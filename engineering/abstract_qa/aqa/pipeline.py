from __future__ import annotations

import datetime as dt
import json
import os
import platform
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

from . import __version__, census, checks, federal, inventory, reconcile, safety, style, tables
from .util import (fingerprint, norm_compare, read_json, sha256_file, write_new_csv, write_new_json,
                   write_new_text)

UNASSIGNED = "UNASSIGNED"


def section_of(path: str, cfg: dict[str, Any]) -> tuple[str, str]:
    for rule in cfg["section_rules"]:
        m = re.search(rule["regex"], path)
        if m:
            gd = m.groupdict()
            return (gd.get("section") or UNASSIGNED).upper(), gd.get("county") or ""
    return UNASSIGNED, ""


class Run:
    """A run directory. Stage outputs are content-addressed, so nothing is ever rewritten."""

    def __init__(self, cfg: dict[str, Any], run_id: str | None, resume: bool):
        self.cfg = cfg
        self.run_id = run_id or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", self.run_id):
            raise ValueError("run id must be 1-64 chars of [A-Za-z0-9_.-]")
        self.out_root = Path(os.path.abspath(os.path.expanduser(cfg["output_root"])))
        self.run_dir = self.out_root / "runs" / self.run_id
        if resume:
            if not self.run_dir.is_dir():
                raise FileNotFoundError(f"cannot resume; no run {self.run_dir}")
        else:
            if self.run_dir.exists():
                raise FileExistsError(f"run directory already exists (no overwrite): {self.run_dir}")
            self.run_dir.mkdir(parents=True)
        self.guard = safety.OutputGuard(self.run_dir, cfg["protected_paths"], cfg["source_roots"])
        self.cfg_fp = fingerprint({k: v for k, v in cfg.items() if k not in ("output_root",)})
        self.receipts: list[dict[str, Any]] = []
        self.reused: list[str] = []

    def stage_dir(self, name: str, fp: str) -> Path:
        return self.guard.check(self.run_dir / "stages" / name / fp[:16])

    def stage(self, name: str, input_fp: str, fn: Callable[[], dict[str, Any]]) -> tuple[dict[str, Any], str]:
        d = self.stage_dir(name, input_fp)
        res_path, rec_path = d / "result.json", d / "receipt.json"
        if rec_path.exists() and res_path.exists():
            rec = read_json(rec_path)
            if rec["input_fingerprint"] == input_fp and sha256_file(res_path) == rec["result_sha256"]:
                self.reused.append(name)
                self.receipts.append(rec)
                return read_json(res_path), rec["result_sha256"]
        started = dt.datetime.now(dt.timezone.utc).isoformat()
        result = fn()
        d.mkdir(parents=True, exist_ok=True)
        if res_path.exists():  # partial earlier attempt: park it rather than overwrite
            res_path.rename(d / f"result.stale.{started.replace(':', '')}.json")
        sha = write_new_json(self.guard.check(res_path), result)
        rec = {"stage": name, "input_fingerprint": input_fp, "result_sha256": sha, "started": started,
               "ended": dt.datetime.now(dt.timezone.utc).isoformat(), "tool_version": __version__,
               "python": platform.python_version(), "status": "ok"}
        if rec_path.exists():
            rec_path.rename(d / f"receipt.stale.{started.replace(':', '')}.json")
        write_new_json(self.guard.check(rec_path), rec)
        self.receipts.append(rec)
        return result, sha


# ----------------------------------------------------------------------------- stages

def stage_inventory(cfg: dict[str, Any], run: Run) -> tuple[dict[str, Any], str, dict[str, Any]]:
    cache_path = run.out_root / "cache" / "inventory_cache.jsonl"
    inv = inventory.run_inventory(cfg, cache_path)
    inventory.save_cache(cache_path, inv["cache_records"])
    result = {"entries": inv["entries"], "findings": inv["findings"],
              "cache_hits": inv["cache_hits"], "cache_misses": inv["cache_misses"]}
    ifp = fingerprint(result["entries"])
    res, sha = run.stage("inventory", ifp, lambda: result)
    return res, sha, inv


def stage_tables(cfg: dict[str, Any], entries: list[dict[str, Any]]) -> dict[str, Any]:
    recs: list[dict[str, Any]] = []
    rows_out: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    for e in entries:
        if e["ext"] not in inventory.TABLE_EXT or not e.get("sha256"):
            continue
        if e["size"] > cfg["max_parse_bytes"]:
            findings.append(safety.finding("WARN", "TABLE_FILE_TOO_LARGE", f"not parsed: {e['path']}", path=e["path"]))
            continue
        section, county = section_of(e["path"], cfg)
        try:
            data = inventory.open_entry_bytes(cfg, e["path"])
            tbls, fmeta = tables.read_tables(e["ext"], data, load_format=True)
        except Exception as exc:
            findings.append(safety.finding("BLOCK", "TABLE_PARSE_FAILED", f"{e['path']}: {type(exc).__name__}: {exc}"[:300],
                                           path=e["path"], section=section))
            continue
        if not tbls:
            findings.append(safety.finding("WARN", "NO_TABLES_IN_FILE", e["path"], path=e["path"], section=section))
        for t in tbls:
            cr = tables.count_rows(t["rows"], cfg, e["path"])
            name_kind = tables.kind_from_name(e["path"], cfg)
            kind = cr["kind_by_header"] or name_kind
            if cr["kind_by_header"] and name_kind and cr["kind_by_header"] != name_kind:
                findings.append(safety.finding("WARN", "KIND_NAME_HEADER_DISAGREE",
                                               f"{e['path']}: header says {cr['kind_by_header']}, name says {name_kind}",
                                               path=e["path"], section=section))
            hdr = cr["header"]
            keys, seen = [], defaultdict(int)
            for i, h in enumerate(hdr):
                h = h or f"col{i + 1}"
                seen[h] += 1
                keys.append(h if seen[h] == 1 else f"{h}#{seen[h]}")
            rec = {
                "file": e["path"], "sha256": e["sha256"], "ext": e["ext"], "mtime_ns": e.get("mtime_ns"),
                "section": section, "county": county, "table": t["name"], "kind": kind,
                "header_row": cr["header_row"], "header": hdr, "header_recognised": cr["header_recognised"],
                "raw_rows": cr["raw_rows"], "data_rows": cr["data_rows"], "excluded": cr["excluded"],
                "file_meta": fmeta,
            }
            recs.append(rec)
            for r, no in zip(cr["rows"], cr["row_numbers"]):
                fields = {k: (r[i] if i < len(r) else "") for i, k in enumerate(keys)}
                rows_out.append({"file": e["path"], "table": t["name"], "row_no": no, "section": section,
                                 "county": county, "kind": kind, "fields": fields, "cells": r})
    census.select_tables(recs)
    sel = {(r["file"], r["table"]): r["selected"] for r in recs}
    dup = {(r["file"], r["table"]): (r["duplicate_of"], r["superseded_by"]) for r in recs}
    for r in rows_out:
        k = (r["file"], r["table"])
        r["selected"] = sel[k]
    return {"tables": recs, "rows": rows_out, "findings": findings}


def stage_checks(cfg: dict[str, Any], entries: list[dict[str, Any]], tb: dict[str, Any]) -> dict[str, Any]:
    pdfs = checks.PdfIndex(entries)
    schema_results, ref_findings = [], []
    for r in tb["tables"]:
        sr = checks.test_schema(r["header"], r["kind"], cfg)
        fh = checks.forbidden_header_hits(r["header"], cfg)
        schema_results.append({"file": r["file"], "table": r["table"], "section": r["section"], "kind": r["kind"],
                               "selected": r["selected"], "schema": sr, "forbidden_headers": fh})
    by_table = {(r["file"], r["table"]): r for r in tb["tables"]}
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in tb["rows"]:
        grouped[(row["file"], row["table"])].append(row)
    for (f, t), rs in grouped.items():
        rec = by_table[(f, t)]
        cells = [x["cells"] for x in rs]
        nos = [x["row_no"] for x in rs]
        for hit in checks.forbidden_value_hits(cells, nos, cfg):
            ref_findings.append({"code": "FORBIDDEN_VALUE", "detail": f"col{hit['col']}: {hit['value']}", "file": f,
                                 "table": t, "row": hit["row"], "section": rec["section"], "selected": rec["selected"]})
        schema = checks.schema_for(rec["kind"], cfg)
        if schema:
            for no in checks.extra_width_rows(cells, nos, len(schema)):
                ref_findings.append({"code": "DATA_BEYOND_SCHEMA_WIDTH", "detail": f"data past column {len(schema)}",
                                     "file": f, "table": t, "row": no, "section": rec["section"], "selected": rec["selected"]})
        for x in rs:
            for fnd in checks.check_row_refs(x["fields"], pdfs, cfg):
                ref_findings.append({**fnd, "file": f, "table": t, "row": x["row_no"],
                                     "section": rec["section"], "selected": rec["selected"]})
    for sr in schema_results:
        for h in sr["forbidden_headers"]:
            ref_findings.append({"code": "FORBIDDEN_HEADER", "detail": h, "file": sr["file"], "table": sr["table"],
                                 "row": None, "section": sr["section"], "selected": sr["selected"]})
    return {"schema": schema_results, "ref_findings": ref_findings}


def stage_analysis(cfg: dict[str, Any], entries: list[dict[str, Any]], tb: dict[str, Any]) -> dict[str, Any]:
    rows = tb["rows"]
    sel_rows = [r for r in rows if r["selected"]]
    recon = reconcile.reconcile(sel_rows, cfg)
    ident = {(r["file"], r["table"], r["row_no"]): r.get("identity") for r in sel_rows}
    for r in rows:
        r["identity"] = ident.get((r["file"], r["table"], r["row_no"]))
    ledger = federal.build_ledger(sel_rows, cfg)
    units = census.counting_units(entries, rows, recon, ledger, cfg)
    expl = census.explain_difference(cfg["claimed_placements"], tb["tables"], units["index_placements_total"])
    selected_tables = [t for t in tb["tables"] if t["selected"] and t["kind"] in ("county", "federal")]
    sty = style.compare_to_donor(selected_tables, cfg)
    return {"reconciliation": recon, "federal": ledger, "units": units, "census_explanation": expl, "style": sty}


# ------------------------------------------------------------------------ dashboard

def section_summary(cfg, entries, tb, ck, an, global_blockers) -> list[dict[str, Any]]:
    secs: dict[str, dict[str, Any]] = {}

    def S(name: str) -> dict[str, Any]:
        return secs.setdefault(name, {
            "section": name, "table_files_selected": 0, "table_files_superseded_or_dup": 0, "data_rows": 0,
            "pdf_files": 0, "pdf_pages": 0, "schema_not_exact": 0, "forbidden": 0, "false_parts": 0,
            "page_ref_problems": 0, "field_conflicts": 0, "probable_omissions": 0, "review_missing": 0,
            "true_duplicates": 0, "no_identity_rows": 0, "style_unexplained": 0, "read_errors": 0, "blockers": [], "info": []})

    for t in tb["tables"]:
        s = S(t["section"])
        if t["selected"]:
            s["table_files_selected"] += 1
            s["data_rows"] += t["data_rows"]
        else:
            s["table_files_superseded_or_dup"] += 1
    for e in entries:
        if e["ext"] == ".pdf":
            s = S(section_of(e["path"], cfg)[0])
            s["pdf_files"] += 1
            s["pdf_pages"] += e["pdf_pages"] or 0
        if e["errors"] or e.get("skipped"):
            S(section_of(e["path"], cfg)[0])["read_errors"] += 1
    for r in ck["schema"]:
        if r["selected"] and r["kind"] in ("county", "federal") and not r["schema"]["exact"]:
            S(r["section"])["schema_not_exact"] += 1
        if r["selected"] and r["kind"] not in ("county", "federal"):
            S(r["section"])["schema_not_exact"] += 1
    for f in ck["ref_findings"]:
        if not f["selected"]:
            continue
        s = S(f["section"])
        c = f["code"]
        if c in ("FORBIDDEN_HEADER", "FORBIDDEN_VALUE", "DATA_BEYOND_SCHEMA_WIDTH"):
            s["forbidden"] += 1
        elif c == "FALSE_PART_NUMBER":
            s["false_parts"] += 1
        else:
            s["page_ref_problems"] += 1
    rc = an["reconciliation"]
    for c in rc["conflicts"]:
        for sec in c["sections"]:
            S(sec)["field_conflicts"] += 1
    for m in rc["candidate_missing"]:
        k = "probable_omissions" if m["classification"].startswith("probable") else "review_missing"
        S(m["missing_in"])[k] += 1
    for d in rc["within_section_duplicates"]:
        S(d["section"])["true_duplicates"] += 1
    for n in rc["no_identity_rows"]:
        S(n["section"])["no_identity_rows"] += 1
    for row in an["style"]["sections"]:
        S(row["section"])["style_unexplained"] += sum(1 for d in row["deviations"] if d["state"] == "unexplained")
    for s in secs.values():
        has_tables = s["table_files_selected"] + s["table_files_superseded_or_dup"] > 0
        if s["table_files_selected"] == 0 and (s["section"] != UNASSIGNED or has_tables):
            s["blockers"].append("no selected table file")
        elif s["section"] == UNASSIGNED and not has_tables:
            s["info"].append("source files outside any configured section (shared pool); no tables")
        if s["section"] == UNASSIGNED and has_tables:
            s["blockers"].append("table files not assignable to a section (fix section_rules)")
        for k, label in (("schema_not_exact", "schema not exact"), ("forbidden", "forbidden/overwide entries"),
                         ("false_parts", "false Part numbers"), ("page_ref_problems", "invalid page/source refs"),
                         ("field_conflicts", "cross-section field conflicts"), ("probable_omissions", "probable omissions"),
                         ("true_duplicates", "in-section duplicates"), ("no_identity_rows", "rows without recorder identity"),
                         ("style_unexplained", "unexplained style deviations vs donor"), ("read_errors", "unreadable/skipped sources")):
            if s[k]:
                s["blockers"].append(f"{label}: {s[k]}")
        if s["review_missing"]:
            s["info"].append(f"possible legitimate gaps to review: {s['review_missing']}")
        s["status"] = "BLOCKED" if (s["blockers"] or global_blockers) else "AUTOMATED CHECKS CLEAR - IMAGE REVIEW PENDING"
    return [secs[k] for k in sorted(secs)]


def render_dashboard(meta: dict[str, Any], sections: list[dict[str, Any]], an: dict[str, Any],
                     safety_findings: list[dict[str, Any]]) -> str:
    from html import escape as h

    def kv(d: dict[str, Any]) -> str:
        return "".join(f"<tr><th>{h(str(k))}</th><td>{h(str(v))}</td></tr>" for k, v in d.items())

    cols = ["section", "status", "table_files_selected", "data_rows", "pdf_files", "pdf_pages", "schema_not_exact",
            "forbidden", "false_parts", "page_ref_problems", "field_conflicts", "probable_omissions", "review_missing",
            "true_duplicates", "no_identity_rows", "style_unexplained", "read_errors"]
    head = "".join(f"<th>{h(c.replace('_', ' '))}</th>" for c in cols)
    body = ""
    for s in sections:
        cls = "bad" if s["status"] == "BLOCKED" else "ok"
        tds = "".join(f"<td>{h(str(s[c]))}</td>" for c in cols)
        why = "; ".join(s["blockers"] + s["info"])
        body += f"<tr class='{cls}'>{tds}</tr>" + (f"<tr class='why'><td colspan='{len(cols)}'>{h(why)}</td></tr>" if why else "")
    blocks = [f for f in safety_findings if f["level"] == "BLOCK"]
    sf = "".join(f"<tr class='{'bad' if f['level'] == 'BLOCK' else ''}'><td>{h(f['level'])}</td><td>{h(f['code'])}</td><td>{h(f['detail'])}</td></tr>"
                 for f in safety_findings if f["level"] != "INFO") or "<tr><td colspan=3>none</td></tr>"
    ex = an["census_explanation"]
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Abstract QA Dashboard</title><style>
:root{{--bg:#fff;--fg:#1b1f24;--mut:#59636e;--line:#d0d7de;--bad:#ffebe9;--ok:#dafbe1;--warn:#fff8c5}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0d1117;--fg:#e6edf3;--mut:#9198a1;--line:#30363d;--bad:#3d1d20;--ok:#12261e;--warn:#3a2f00}}}}
body{{background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,sans-serif;margin:0;padding:16px}}
h1{{font-size:20px}}h2{{font-size:16px;margin-top:28px}}table{{border-collapse:collapse;width:100%;font-size:12.5px}}
th,td{{border:1px solid var(--line);padding:4px 8px;text-align:left;vertical-align:top}}
.wrap{{overflow-x:auto}}tr.bad td{{background:var(--bad)}}tr.ok td{{background:var(--ok)}}tr.why td{{background:var(--warn);color:var(--fg)}}
.note{{color:var(--mut)}}</style></head><body>
<h1>Abstract QA Dashboard - run {h(meta['run_id'])}</h1>
<p class="note">Automated evidence only. Substantive title facts come from the original images. "Clear" never means complete or verified.</p>
<p><b>Global blockers: {len(blocks)}</b></p>
<h2>Per-section completion</h2><div class="wrap"><table><tr>{head}</tr>{body}</table></div>
<h2>Counting units (selected files, from bytes)</h2><div class="wrap"><table>{kv(an['units'])}</table></div>
<h2>Census explanation</h2><div class="wrap"><table>{kv({k: v for k, v in ex.items() if k != 'categories'})}{kv(ex['categories'])}</table></div>
<h2>Safety findings</h2><div class="wrap"><table><tr><th>level</th><th>code</th><th>detail</th></tr>{sf}</table></div>
<h2>Run</h2><div class="wrap"><table>{kv(meta)}</table></div></body></html>"""


# --------------------------------------------------------------------------- driver

def previous_inventory(run: Run, cfg: dict[str, Any]) -> list[dict[str, Any]] | None:
    if cfg["baseline_manifest"]:
        return read_json(Path(cfg["baseline_manifest"]))["entries"]
    runs = sorted(p for p in (run.out_root / "runs").glob("*") if p.is_dir() and p.name < run.run_id)
    for rd in reversed(runs):
        for res in sorted((rd / "stages" / "inventory").glob("*/result.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            return read_json(res)["entries"]
    return None


def execute(cfg: dict[str, Any], run_id: str | None = None, resume: bool = False) -> dict[str, Any]:
    pre = safety.preflight(cfg)
    if any(f["level"] == "BLOCK" and f["code"] in ("OUTPUT_OVERLAPS_SOURCE", "OUTPUT_OVERLAPS_PROTECTED", "OUTPUT_IN_CLOUD_SYNC") for f in pre):
        # nothing is created; refuse before touching the disk
        return {"run_dir": None, "status": "REFUSED", "findings": pre}
    run = Run(cfg, run_id, resume)
    res_inv, inv_sha, inv_raw = stage_inventory(cfg, run)
    entries = res_inv["entries"]
    sfind = list(pre) + list(res_inv["findings"])
    tfp = fingerprint([inv_sha, run.cfg_fp, "tables"])
    tb, tb_sha = run.stage("tables", tfp, lambda: stage_tables(cfg, entries))
    cfp = fingerprint([inv_sha, tb_sha, run.cfg_fp, "checks"])
    ck, ck_sha = run.stage("checks", cfp, lambda: stage_checks(cfg, entries, tb))
    afp = fingerprint([tb_sha, run.cfg_fp, "analysis"])
    an, an_sha = run.stage("analysis", afp, lambda: stage_analysis(cfg, entries, tb))

    sfind += tb["findings"]
    sfind += safety.mutation_check(inv_raw["stats_before"])
    sfind += safety.check_expected(cfg["expected_sources"], entries)
    prev = previous_inventory(run, cfg)
    if prev is not None:
        sfind += safety.compare_manifests(prev, entries)
    elif not cfg["expected_sources"]:
        sfind.append(safety.finding("WARN", "NO_BASELINE", "no baseline manifest or expected_sources; disappearance cannot be detected on this run"))
    global_blockers = [f for f in sfind if f["level"] == "BLOCK"]
    sections = section_summary(cfg, entries, tb, ck, an, global_blockers)

    final_fp = fingerprint([inv_sha, tb_sha, ck_sha, an_sha, sorted(f["code"] + f["detail"] for f in sfind)])
    fdir = run.guard.check(run.run_dir / f"final-{final_fp[:12]}")
    meta = {"run_id": run.run_id, "tool_version": __version__, "python": platform.python_version(),
            "config_fingerprint": run.cfg_fp, "stages_reused": ",".join(run.reused) or "none",
            "inventory_cache_hits": res_inv["cache_hits"], "inventory_cache_misses": res_inv["cache_misses"],
            "project_label": cfg["project_label"]}
    status = "BLOCKED" if (global_blockers or any(s["status"] == "BLOCKED" for s in sections)) else "AUTOMATED_CHECKS_CLEAR_IMAGE_REVIEW_PENDING"
    if fdir.exists():
        return {"run_dir": str(run.run_dir), "final_dir": str(fdir), "status": status, "reused_final": True, "sections": sections}
    fdir.mkdir(parents=True)
    hashes: dict[str, str] = {}

    def wj(name: str, obj: Any) -> None:
        hashes[name] = write_new_json(run.guard.check(fdir / name), obj)

    def wc(name: str, header: list[str], rows: list[list[Any]]) -> None:
        hashes[name] = write_new_csv(run.guard.check(fdir / name), header, rows)

    wj("inventory.json", {"entries": entries})
    wc("inventory.csv", ["path", "ext", "size", "sha256", "crc32", "pdf_pages", "pdf_images", "image_frames", "container", "errors"],
       [[e["path"], e["ext"], e["size"], e["sha256"], e["crc32"], e["pdf_pages"], e["pdf_images"], e["image_frames"],
         e["container"], "; ".join(e["errors"])] for e in entries])
    wj("tables.json", {"tables": [{k: v for k, v in t.items() if k != "file_meta"} for t in tb["tables"]],
                       "file_meta": {t["file"]: t["file_meta"] for t in tb["tables"]}})
    wj("schema_checks.json", ck["schema"])
    wc("reference_findings.csv", ["code", "detail", "file", "table", "row", "section", "selected"],
       [[f["code"], f["detail"], f["file"], f["table"], f["row"], f["section"], f["selected"]] for f in ck["ref_findings"]])
    wj("reconciliation.json", an["reconciliation"])
    wc("candidate_missing.csv", ["group", "identity", "missing_in", "present_in", "classification", "status"],
       [[m["group"], m["identity"], m["missing_in"], "|".join(m["present_in"]), m["classification"], m["status"]]
        for m in an["reconciliation"]["candidate_missing"]])
    wc("field_conflicts.csv", ["identity", "sections", "field", "values", "status"],
       [[c["identity"], "|".join(c["sections"]), fc["field"], json.dumps(fc["values"], sort_keys=True), c["status"]]
        for c in an["reconciliation"]["conflicts"] for fc in c["conflicts"]])
    wj("federal_ledger.json", an["federal"])
    sch = cfg["federal_schema"]
    wc("federal_ledger.csv", ["ledger_id", *sch, "sections", "appearances", "status", "conflicting_fields"],
       [[e["ledger_id"], *[e["fields"].get(f, "") for f in sch], "|".join(e["sections"]), e["appearances"], e["status"],
         json.dumps(e["conflicts"], sort_keys=True) if e["conflicts"] else ""] for e in an["federal"]["ledger"]])
    wj("census.json", {"units": an["units"], "explanation": an["census_explanation"]})
    wj("style_comparison.json", an["style"])
    wj("safety.json", sfind)
    wj("section_dashboard.json", sections)
    hashes["qa_dashboard.html"] = write_new_text(run.guard.check(fdir / "qa_dashboard.html"), render_dashboard(meta, sections, an, sfind))
    receipt = {
        "run_id": run.run_id, "status": status, "tool_version": __version__, "python": platform.python_version(),
        "config_fingerprint": run.cfg_fp, "stage_receipts": run.receipts, "stages_reused": run.reused,
        "artifact_sha256": hashes, "global_blockers": len(global_blockers),
        "sections": {s["section"]: s["status"] for s in sections},
        "claim_policy": "Automated checks only; no completion is asserted. Title facts require original-image review.",
    }
    write_new_json(run.guard.check(fdir / "qa_receipt.json"), receipt)
    return {"run_dir": str(run.run_dir), "final_dir": str(fdir), "status": status, "sections": sections,
            "units": an["units"], "explanation": an["census_explanation"]}


def verify_receipt(final_dir: str | Path) -> list[str]:
    fd = Path(final_dir)
    rec = read_json(fd / "qa_receipt.json")
    bad = []
    for name, sha in rec["artifact_sha256"].items():
        p = fd / name
        if not p.exists():
            bad.append(f"missing {name}")
        elif sha256_file(p) != sha:
            bad.append(f"hash mismatch {name}")
    return bad
