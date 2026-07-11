#!/usr/bin/env python3
"""DataBossX registry builder (CAP_SELF_BUILDER / CAP_COMMAND_CENTER).

Scans the repository for code assets, merges the curated knowledge recovered
from the Google Drive workspace (``databossx/data/curated_knowledge.json``),
and emits the canonical DataBossX registry files into ``registry/``:

    MASTER_INVENTORY.jsonl   every scanned asset: path, sha256, size, capabilities
    CAPABILITY_REGISTRY.json capability -> assets implementing it
    PROJECT_GRAPH.json       client -> project -> report relationships
    KNOWLEDGE_GRAPH.json     typed nodes + edges (project/county/section/lease/well/...)
    MASTER_BUILD_QUEUE.json  ranked backlog
    TOOLS.json               runnable tools (repo + Drive workspace)
    PROMPTS.json             recovered AI prompts
    REPORTS.json             report versions and which one is canonical
    CLIENTS.json             client registry
    QA_REPORT.json           test-suite result recorded at build time
    CHANGELOG.md             append-only build log

Stdlib only; deterministic given the same tree and inputs. Rerunnable:
``python -m databossx.build_registry [--repo-root PATH] [--qa "summary"]``.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
from pathlib import Path
from typing import Dict, Iterable, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = Path(__file__).resolve().parent / "data" / "curated_knowledge.json"

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".devcontainer", ".emergent",
             "registry", "logs", ".pytest_cache"}
SKIP_SUFFIXES = {".pyc", ".lock", ".log", ".db"}

# Capability classification by path pattern (checked in order; first match set wins,
# multiple rules may match and all their capabilities are unioned).
CAPABILITY_RULES: List[tuple] = [
    ("horizon/interest",        ["CAP_WI", "CAP_TITLE_CHAIN"]),
    ("horizon/chaining",        ["CAP_TITLE_CHAIN", "CAP_MINERAL_CHAIN"]),
    ("horizon/validation",      ["CAP_QA"]),
    ("horizon/repair",          ["CAP_QA", "CAP_AUTOMATION"]),
    ("horizon/orchestrator",    ["CAP_COMMAND_CENTER", "CAP_AUTOMATION"]),
    ("horizon/pipeline",        ["CAP_REPORT", "CAP_WORKBOOK"]),
    ("horizon/report_io",       ["CAP_REPORT", "CAP_WORKBOOK"]),
    ("horizon/artifacts",       ["CAP_REPORT"]),
    ("horizon/audit",           ["CAP_QA"]),
    ("horizon/",                ["CAP_COMMAND_CENTER"]),
    ("grocery_report_pipeline", ["CAP_OCR", "CAP_INDEX_EXTRACTION", "CAP_INSTRUMENT_EXTRACTION",
                                 "CAP_REPORT", "CAP_QA", "CAP_AUTOMATION"]),
    ("roger_mills_title_report_builder", ["CAP_WORKBOOK", "CAP_REPORT"]),
    ("automation/parsing",      ["CAP_INSTRUMENT_EXTRACTION"]),
    ("automation/status_logic", ["CAP_OGL"]),
    ("automation/writer",       ["CAP_REPORT"]),
    ("automation/playwright_bot", ["CAP_RESEARCH", "CAP_AUTOMATION"]),
    ("doto_image_commander/processors/ocr", ["CAP_OCR", "CAP_VISION"]),
    ("doto_image_commander/processors/pdf", ["CAP_OCR"]),
    ("doto_image_commander/api/okcounty",   ["CAP_RESEARCH", "CAP_INDEX_EXTRACTION"]),
    ("doto_image_commander/reports",        ["CAP_REPORT"]),
    ("doto_image_commander/",   ["CAP_AUTOMATION"]),
    ("mineral_deal_room/",      ["CAP_COMMAND_CENTER"]),
    ("databossx/okcounty",      ["CAP_RESEARCH", "CAP_INDEX_EXTRACTION", "CAP_AUTOMATION"]),
    ("databossx/workbook_qa",   ["CAP_QA", "CAP_WORKBOOK"]),
    ("databossx/data/evidence_pull_queue", ["CAP_RESEARCH"]),
    ("databossx/",              ["CAP_SELF_BUILDER", "CAP_COMMAND_CENTER"]),
    ("tests/",                  ["CAP_QA"]),
    ("backend/",                ["CAP_AUTOMATION"]),
    ("frontend/",               ["CAP_COMMAND_CENTER"]),
]

DOC_KINDS = {".md": "doc", ".txt": "doc", ".json": "data", ".jsonl": "data",
             ".toml": "config", ".yml": "config", ".yaml": "config"}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _classify(rel: str) -> List[str]:
    caps: List[str] = []
    for pattern, rule_caps in CAPABILITY_RULES:
        if pattern in rel:
            for c in rule_caps:
                if c not in caps:
                    caps.append(c)
    return caps or ["UNCLASSIFIED"]


def _kind(path: Path) -> str:
    if path.suffix == ".py":
        return "test" if path.name.startswith("test_") else "tool"
    if path.suffix in (".ts", ".tsx", ".js", ".jsx"):
        return "tool"
    return DOC_KINDS.get(path.suffix, "asset")


def scan_repo(root: Path) -> List[Dict]:
    """Walk the repo and return inventory records for every tracked-worthy file."""
    records: List[Dict] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        for name in sorted(filenames):
            p = Path(dirpath) / name
            if p.suffix in SKIP_SUFFIXES or name.startswith("."):
                continue
            rel = p.relative_to(root).as_posix()
            try:
                size = p.stat().st_size
            except OSError:
                continue
            records.append({
                "asset": rel,
                "store": "repo",
                "kind": _kind(p),
                "size_bytes": size,
                "sha256": _sha256(p),
                "capabilities": _classify(rel),
            })
    return records


def load_curated(data_file: Path = DATA_FILE) -> Dict:
    with open(data_file, "r", encoding="utf-8") as fh:
        return json.load(fh)


def drive_inventory(curated: Dict) -> List[Dict]:
    """Inventory records for known Drive-workspace assets (curated snapshot)."""
    ws = curated["drive_workspace"]
    records: List[Dict] = []
    for folder in ws["structure"]:
        records.append({"asset": folder, "store": "drive", "kind": "folder",
                        "capabilities": ["CAP_PLAYBOOK"], "drive_workspace": ws["folder_id"]})
    for tool in ws["tools"]:
        records.append({"asset": tool["title"], "store": "drive", "kind": "tool",
                        "drive_file_id": tool["drive_file_id"], "status": tool["status"],
                        "capabilities": ["CAP_WORKBOOK", "CAP_QA"]})
    for prompt in ws["prompts"]:
        records.append({"asset": prompt["title"], "store": "drive", "kind": "prompt",
                        "drive_file_id": prompt["drive_file_id"], "status": prompt["status"],
                        "capabilities": ["CAP_PLAYBOOK"]})
    for rpt in curated["reports"]:
        rec = {"asset": rpt["title"], "store": "drive", "kind": "report",
               "capabilities": ["CAP_REPORT"], "role": rpt["role"]}
        if rpt.get("sha256"):
            rec["sha256"] = rpt["sha256"].lower()
        if rpt.get("drive_file_id"):
            rec["drive_file_id"] = rpt["drive_file_id"]
        records.append(rec)
    return records


def capability_registry(inventory: Iterable[Dict]) -> Dict[str, List[str]]:
    reg: Dict[str, List[str]] = {}
    for rec in inventory:
        for cap in rec["capabilities"]:
            reg.setdefault(cap, []).append(rec["asset"])
    return {cap: sorted(assets) for cap, assets in sorted(reg.items())}


def project_graph(curated: Dict) -> Dict:
    return {
        "clients": curated["clients"],
        "projects": curated["projects"],
        "reports": curated["reports"],
    }


def knowledge_graph(curated: Dict) -> Dict:
    nodes: List[Dict] = []
    edges: List[Dict] = []
    for c in curated["clients"]:
        nodes.append({"type": "Client", "id": c["id"], "label": c["name"]})
    for p in curated["projects"]:
        nodes.append({"type": "Project", "id": p["id"], "label": p["name"], "status": p.get("status")})
        if p.get("client"):
            edges.append({"from": p["id"], "to": p["client"], "rel": "for_client"})
        if p.get("county"):
            county_id = "COUNTY_" + p["county"].upper().replace(" ", "_")
            if not any(n["id"] == county_id for n in nodes):
                nodes.append({"type": "County", "id": county_id,
                              "label": f"{p['county']} County, {p.get('state', '')}".strip()})
            edges.append({"from": p["id"], "to": county_id, "rel": "in_county"})
        if p.get("section"):
            sec_id = f"SECTION_{p['section']}_{p['township']}_{p['range']}"
            nodes.append({"type": "Section", "id": sec_id,
                          "label": f"Section {p['section']}-{p['township']}-{p['range']}"})
            edges.append({"from": p["id"], "to": sec_id, "rel": "covers"})
    for n in curated["knowledge_graph_extra_nodes"]:
        node = {k: v for k, v in n.items() if k not in ("project", "source")}
        node["source"] = n.get("source")
        nodes.append(node)
        if n.get("project"):
            edges.append({"from": n["project"], "to": n["id"], "rel": "has_" + n["type"].lower()})
    for r in curated["reports"]:
        nodes.append({"type": "Report", "id": r["id"], "label": r["title"], "role": r["role"]})
        edges.append({"from": r["project"], "to": r["id"], "rel": "produced"})
    for oi in curated["open_items"]:
        nodes.append({"type": "OpenItem", "id": oi["id"], "label": oi["item"],
                      "priority": oi["priority"], "source": oi["source"]})
        edges.append({"from": "PROJ_32_11N_25W_DIVERSIFIED", "to": oi["id"], "rel": "blocked_by"})
    return {"nodes": nodes, "edges": edges}


def build_all(repo_root: Path = REPO_ROOT, out_dir: Optional[Path] = None,
              qa_summary: Optional[str] = None, timestamp: Optional[str] = None,
              data_file: Path = DATA_FILE) -> Dict[str, Path]:
    """Build every registry file. Returns {name: written_path}."""
    out = out_dir or (repo_root / "registry")
    out.mkdir(parents=True, exist_ok=True)
    curated = load_curated(data_file)
    stamp = timestamp or _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")

    inventory = scan_repo(repo_root) + drive_inventory(curated)
    written: Dict[str, Path] = {}

    def emit(name: str, payload) -> None:
        path = out / name
        with open(path, "w", encoding="utf-8") as fh:
            if name.endswith(".jsonl"):
                for rec in payload:
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            else:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
                fh.write("\n")
        written[name] = path

    emit("MASTER_INVENTORY.jsonl", inventory)
    emit("CAPABILITY_REGISTRY.json", {"generated": stamp, "capabilities": capability_registry(inventory)})
    emit("PROJECT_GRAPH.json", {"generated": stamp, **project_graph(curated)})
    emit("KNOWLEDGE_GRAPH.json", {"generated": stamp, **knowledge_graph(curated)})
    emit("MASTER_BUILD_QUEUE.json", {"generated": stamp, "queue": curated["build_queue"],
                                     "open_items": curated["open_items"]})
    emit("TOOLS.json", {"generated": stamp,
                        "tools": [r for r in inventory if r["kind"] == "tool"]})
    emit("PROMPTS.json", {"generated": stamp,
                          "prompts": [r for r in inventory if r["kind"] == "prompt"]})
    emit("REPORTS.json", {"generated": stamp, "reports": curated["reports"]})
    emit("CLIENTS.json", {"generated": stamp, "clients": curated["clients"]})
    emit("QA_REPORT.json", {"generated": stamp,
                            "test_suite": qa_summary or "not run at build time",
                            "canonical_report_qa": [r.get("qa") for r in curated["reports"] if r.get("qa")]})

    queue_file = data_file.parent / "evidence_pull_queue.json"
    if queue_file.exists():
        with open(queue_file, "r", encoding="utf-8") as fh:
            emit("EVIDENCE_PULL_QUEUE.json", json.load(fh))

    changelog = out / "CHANGELOG.md"
    header = "" if changelog.exists() else "# DataBossX Registry Changelog\n\n"
    with open(changelog, "a", encoding="utf-8") as fh:
        fh.write(f"{header}- {stamp} — registry rebuilt: {len(inventory)} assets "
                 f"({sum(1 for r in inventory if r['store'] == 'repo')} repo, "
                 f"{sum(1 for r in inventory if r['store'] == 'drive')} drive); "
                 f"QA: {qa_summary or 'n/a'}\n")
    written["CHANGELOG.md"] = changelog
    return written


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--qa", type=str, default=None,
                    help="test-suite result summary to record in QA_REPORT.json")
    args = ap.parse_args(argv)
    written = build_all(args.repo_root, args.out, args.qa)
    for name, path in written.items():
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
