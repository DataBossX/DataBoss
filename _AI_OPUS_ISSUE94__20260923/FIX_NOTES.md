# Issue #94 — smallest production diffs to turn this packet green

Base: `c87d85d` (production files are identical to `2714a24`, which already
contains the first-round Issue #94 fixes from the current writer).

On that base, `test_issue94_integrity.py` + `test_backend_security.py` give
**15 failed / 130 passed**. With the patch below applied to a scratch copy
(`/tmp/issue94_fix`, never `/workspace`), the result is **317 passed**. That
count covers the full existing `tests/` suite plus both packet modules. The
patch passes `git apply --check` against `/workspace` at `c87d85d`, and
`pyflakes` is clean on every touched file.

Total patch: 5 files, +75 / −21.

## What each hunk closes

| Remaining gap on `c87d85d` | Failing packet test(s) | Hunk |
|---|---|---|
| `Orchestrator.run` converges on a passing in-memory model and calls `emit_version(template=current)`. That copies the ingested `#REF!` sheet into the new version (media path). | `test_errored_workbook_cannot_converge_even_if_model_validates` | `orchestrator.py`: `template_blocked()` gate before both emit sites; `repair.py`: `workbook_defects()` |
| `repair_workbook` accepts any fixer output, so a fixer that drops a row or cell is promoted. | `test_repair_rejects_any_row_or_cell_loss[drop_row, drop_cell]` | `repair.py`: `_cell_inventory()` equality check per worksheet part |
| When lxml is missing, `repair_workbook` copies `src` to `dest` and returns `output=dest` (fail-open). | `test_repair_without_lxml_refuses_instead_of_copying` | `repair.py`: return a refusal, no copy; drop unused `shutil` |
| The recording label regex matches inside `unrecorded`, which fabricates `recording_date`. | `test_recording_date_blank_without_recording_label[r3]` | pipeline: `(?<![A-Za-z])…\b` |
| A blank `recording_date` is review-required only when book/page is also missing. | `test_missing_recording_date_is_review_required[r2, r3]` | pipeline `validate`: `missing-recording-date` (yellow) |
| The `_DECIMAL_RX` branch `1(?:\.0+)?` reads `1.5`, `10.5` and `12` as `1.0`. | `test_out_of_range_decimal_is_not_coerced_to_one[×3]` | pipeline: trailing `(?!\d\|\.\d)` |
| "ownership … decimal interest" plus two or more decimals is treated as a complete owner set, which is a heuristic, not proof. An excerpt then asserts a false 0.75 imbalance. | `test_incomplete_owner_set_asserts_no_sum[ownership_excerpt]` | pipeline: completeness only from `_OWNER_SET_COMPLETE_RX` |
| The self-test corpus relied on that heuristic to flag its 0.95 imbalance. | `test_synthetic_corpus_marks_its_owner_schedule_complete` | pipeline `make_synthetic_corpus`: add explicit "complete owner set" |
| An exact byte-duplicate of a complete schedule is summed twice, giving a false 2.0 conflict. | `test_exact_duplicate_schedule_does_not_double_count` | pipeline: `Fact.sha256` plus per-tract dedupe |
| Auth applies only to `PROTECTED_PREFIXES`, so any route added later is public. | `test_auth_is_default_deny_for_routes_added_later[×2]` | `server.py`: authorize every non-public path |
| The existing `tests/test_issue94_integrity.py` fixture depends on the heuristic above. | `test_ordinary_decimals_parse_and_incomplete_set_does_not_sum` (after the heuristic is removed) | one fixture line: add "complete owner set" |

## Patch (`git apply` from repo root)

```diff
diff --git a/backend/server.py b/backend/server.py
index 659aec6..bfd5f75 100644
--- a/backend/server.py
+++ b/backend/server.py
@@ -54,7 +54,7 @@ def create_app() -> FastAPI:
         path = request.url.path
         if security.is_public_path(path):
             return await call_next(request)
-        if security.is_protected_path(path) and not security.authorized(_header_map(request)):
+        if not security.authorized(_header_map(request)):
             return _generic_error(401, "unauthorized")
         return await call_next(request)
 
diff --git a/grocery_report_pipeline.py b/grocery_report_pipeline.py
index 4c77cdb..70efffa 100644
--- a/grocery_report_pipeline.py
+++ b/grocery_report_pipeline.py
@@ -288,10 +288,7 @@ def _owner_set_is_complete(text: str, decimals: List[float]) -> bool:
     body = text or ""
     if _OWNER_SET_INCOMPLETE_RX.search(body):
         return False
-    if _OWNER_SET_COMPLETE_RX.search(body):
-        return True
-    claimed_schedule = re.search(r"\bownership\b.*\bdecimal interest\b", body, re.I | re.S)
-    return bool(claimed_schedule) and len(decimals) >= 2
+    return bool(_OWNER_SET_COMPLETE_RX.search(body))
 
 
 def _date_near_label(text: str, keyword: str) -> Optional[str]:
@@ -867,7 +864,7 @@ _ROYALTY_RX = re.compile(r"(?:royalty|rr)\s*(?:of|:)?\s*(\d+(?:\.\d+)?%|\d+/\d+)
 _NRI_RX = re.compile(r"(?:net\s+revenue\s+interest|nri)\s*(?:of|:)?\s*(\d+(?:\.\d+)?%?)", re.I)
 _WI_RX = re.compile(r"(?:working\s+interest|wi)\s*(?:of|:)?\s*(\d+(?:\.\d+)?%?)", re.I)
 _DECIMAL_RX = re.compile(
-    r"(?:decimal(?:\s+interest)?)\s*(?:of|:)?\s*(0?\.\d{1,16}|1(?:\.0+)?|0)",
+    r"(?:decimal(?:\s+interest)?)\s*(?:of|:)?\s*(0?\.\d+|1(?:\.0+)?|0)(?!\d|\.\d)",
     re.I,
 )
 _OWNER_SET_COMPLETE_RX = re.compile(
@@ -917,6 +914,7 @@ class Fact:
     all_decimals: List[float] = field(default_factory=list)
     unlabeled_dates: List[str] = field(default_factory=list)
     owner_set_complete: bool = False
+    sha256: str = ""
 
 
 def extract_facts(recs: List[FileRec], texts: Dict[str, TextRec],
@@ -930,7 +928,7 @@ def extract_facts(recs: List[FileRec], texts: Dict[str, TextRec],
         if not text.strip():
             continue
         cats = classes.get(r.path, [])
-        f = Fact(source_file=r.rel_path)
+        f = Fact(source_file=r.rel_path, sha256=r.sha256)
         v = f.values
         c = f.confidence
 
@@ -956,7 +954,7 @@ def extract_facts(recs: List[FileRec], texts: Dict[str, TextRec],
         # a fabricated recording_date (Issue #94).
         for key, kw in [("effective_date", r"effective\s+date"),
                         ("execution_date", r"(?:executed|dated|execution\s+date)"),
-                        ("recording_date", r"(?:recorded|recording\s+date|filed)")]:
+                        ("recording_date", r"(?<![A-Za-z])(?:recorded|recording\s+date|filed)\b")]:
             parsed = _date_near_label(text, kw)
             setv(key, parsed, 0.6 if parsed else 0.0)
         labeled = {v.get("effective_date"), v.get("execution_date"), v.get("recording_date")}
@@ -1112,7 +1110,14 @@ def reconcile(facts: List[Fact], output_dir: Path, log: BuildLog
     conflicts: List[List[Any]] = []
     for legal, group in sorted(tract_groups.items()):
         # Sum ALL decimals found in each doc (multi-owner sheets contribute many).
-        decs = [(d, f) for f in group for d in (f.all_decimals or [])]
+        # Exact byte-duplicates of one schedule must not be summed twice.
+        distinct, seen_sha = [], set()
+        for f in group:
+            if f.sha256 and f.sha256 in seen_sha:
+                continue
+            seen_sha.add(f.sha256)
+            distinct.append(f)
+        decs = [(d, f) for f in distinct for d in (f.all_decimals or [])]
         if not decs:
             decs = [(_to_float(f.values.get("decimal_interest")), f) for f in group
                     if f.values.get("decimal_interest")]
@@ -1208,6 +1213,9 @@ def validate(recs: List[FileRec], texts: Dict[str, TextRec], classes: Dict[str,
         if not f.values.get("book_page_or_instrument") and not f.values.get("recording_date"):
             add("yellow", "missing-recording-data", f.source_file,
                 "No book/page/instrument and no recording date extracted", f.source_file)
+        elif not f.values.get("recording_date"):
+            add("yellow", "missing-recording-date", f.source_file,
+                "No labeled recording date; unlabeled dates are candidates only", f.source_file)
         # impossible dates
         for dk in ("recording_date", "execution_date", "effective_date"):
             if is_impossible_date(f.values.get(dk)):
@@ -1692,7 +1700,7 @@ def make_synthetic_corpus(dest: Path) -> None:
             "Legal: Section 12, T7N, R63W\n"),
         "04_ownership_note.txt": (
             "SYNTHETIC TEST DOCUMENT -- NOT REAL TITLE DATA\n"
-            "OWNERSHIP / mineral owner decimal interest schedule\n"
+            "OWNERSHIP / mineral owner decimal interest schedule -- complete owner set\n"
             "Owner Acme Minerals LLC decimal interest 0.75000000\n"
             "Owner Sample Family Trust decimal interest 0.20000000\n"
             "Legal: Section 12, T7N, R63W\n"),  # sums to 0.95 -> should be flagged
diff --git a/horizon/orchestrator.py b/horizon/orchestrator.py
index 1a49e02..1ce0dbc 100644
--- a/horizon/orchestrator.py
+++ b/horizon/orchestrator.py
@@ -23,7 +23,7 @@ from typing import List, Optional
 from .audit import AuditLog
 from .config import HorizonConfig
 from .models import ReportModel
-from .repair import repair_workbook
+from .repair import repair_workbook, workbook_defects
 from .validation import Requirements, ValidationReport, load_requirements, validate_report
 from .versioning import latest_version, next_version_path
 
@@ -92,6 +92,17 @@ class Orchestrator:
             candidate.unlink()
         return None
 
+    def template_blocked(self, src: Optional[Path]) -> bool:
+        """An errored or malformed workbook must never be carried forward as
+        the template of a converged version."""
+        defects = workbook_defects(src) if src is not None else []
+        if defects:
+            self.audit.escalate(
+                "workbook_defect",
+                f"{src.name}: {', '.join(defects[:5])}; refusing to converge",
+            )
+        return bool(defects)
+
     def emit_version(self, report: ReportModel, base_stem: str, src: Optional[Path]) -> Path:
         """Evaluate step: persist a passing report as a new version."""
         from .report_io import write_report
@@ -119,6 +130,9 @@ class Orchestrator:
             current = self.ingest(base_stem)
             vr = self.validate(working_report, reqs)
 
+            if vr.passed and self.template_blocked(current):
+                result.exhausted = True
+                return result
             if vr.passed:
                 out = self.emit_version(working_report, base_stem, current)
                 result.iterations.append(LoopIteration(
@@ -173,9 +187,9 @@ class Orchestrator:
         # last validation so a workbook that repairs into a passing state
         # converges instead of being wrongly reported as exhausted.
         final_vr = self.validate(working_report, reqs)
-        if final_vr.passed:
-            out = self.emit_version(working_report, base_stem,
-                                    latest_version(self.cfg.final_reports, base_stem))
+        template = latest_version(self.cfg.final_reports, base_stem)
+        if final_vr.passed and not self.template_blocked(template):
+            out = self.emit_version(working_report, base_stem, template)
             result.iterations.append(LoopIteration(
                 index=self.cfg.max_loops + 1,
                 version_in=None, version_out=out.name, passed=True,
diff --git a/horizon/repair.py b/horizon/repair.py
index fb0d9c5..b7f8f03 100644
--- a/horizon/repair.py
+++ b/horizon/repair.py
@@ -16,7 +16,6 @@ non-worksheet parts.
 from __future__ import annotations
 
 import posixpath
-import shutil
 import zipfile
 from copy import deepcopy
 from dataclasses import dataclass, field
@@ -71,6 +70,34 @@ def _cell_is_error_formula(cell) -> bool:
     )
 
 
+def _cell_inventory(xml_bytes: bytes):
+    try:
+        root = etree.fromstring(xml_bytes, parser=etree.XMLParser(recover=False))
+    except etree.XMLSyntaxError as exc:
+        raise RepairDefect("MALFORMED_WORKSHEET_XML", str(exc)) from exc
+    return (
+        [row.get("r") for row in root.iter(f"{{{_MAIN_NS}}}row")],
+        [cell.get("r") for cell in root.iter(f"{{{_MAIN_NS}}}c")],
+    )
+
+
+def workbook_defects(path: Path) -> List[str]:
+    """Strictly scan every worksheet part; empty list means promotable."""
+    defects: List[str] = []
+    try:
+        with zipfile.ZipFile(path) as archive:
+            for name in archive.namelist():
+                if not (name.startswith("xl/worksheets/") and name.endswith(".xml")):
+                    continue
+                try:
+                    _fix_worksheet_xml(archive.read(name), [])
+                except RepairDefect as exc:
+                    defects.append(f"{exc.code}:{name}")
+    except (zipfile.BadZipFile, OSError) as exc:
+        defects.append(f"WORKBOOK_UNREADABLE:{exc}")
+    return defects
+
+
 def _discard(path: Path) -> None:
     if path.exists():
         path.unlink()
@@ -113,10 +140,9 @@ def repair_workbook(
     copied verbatim. ``src`` is never modified.
     """
     if not _HAVE_LXML:
-        # Degrade gracefully: copy through unchanged rather than crash.
-        shutil.copy2(src, dest)
-        return RepairResult(output=dest, repaired=False,
-                            error="lxml unavailable; copied without repair")
+        return RepairResult(output=None, repaired=False,
+                            error="lxml unavailable; repair refused",
+                            defect_code="LXML_UNAVAILABLE")
 
     fixer = worksheet_fixer or _fix_worksheet_xml
     fixes: List[str] = []
@@ -132,7 +158,13 @@ def repair_workbook(
                 if name.startswith("xl/media/"):
                     media += 1
                 if name.startswith("xl/worksheets/") and name.endswith(".xml"):
-                    data = fixer(data, fixes)
+                    fixed = fixer(data, fixes)
+                    if _cell_inventory(fixed) != _cell_inventory(data):
+                        raise RepairDefect(
+                            "CELL_INVENTORY_CHANGED",
+                            f"{name}: repair would add or drop rows/cells",
+                        )
+                    data = fixed
                 # Preserve original metadata (date/compression) for stable output.
                 zout.writestr(item, data)
     except RepairDefect as exc:
diff --git a/tests/test_issue94_integrity.py b/tests/test_issue94_integrity.py
index d802cb0..1958792 100644
--- a/tests/test_issue94_integrity.py
+++ b/tests/test_issue94_integrity.py
@@ -100,7 +100,7 @@ def test_ordinary_decimals_parse_and_incomplete_set_does_not_sum(tmp_path):
     complete = _facts_from_text(
         tmp_path,
         "owners.txt",
-        "SYNTHETIC TEST DOCUMENT\nOWNERSHIP / mineral owner decimal interest schedule\n"
+        "SYNTHETIC TEST DOCUMENT\nOWNERSHIP / mineral owner decimal interest schedule -- complete owner set\n"
         "Owner A decimal interest 0.5\nOwner B decimal interest 0.5\n"
         "Legal: Section 12, T7N, R63W\n",
     )
```

## Updating `test_repair_removes_error_formula_and_preserves_media`

On `582d951` (pre-fix main) this test asserted `result.repaired` and that an
"errored formula" fix was recorded. In other words, it locked in the
downgrade. At `2714a24` the current writer already renamed it to
`test_repair_refuses_error_formula_downgrade` and pinned the refusal. The
recommended final form keeps the media/Zero-Destruction intent, pins the
refusal, and also proves that the source still carries its error, so the
error is never laundered:

```python
@pytest.mark.skipif(not _HAVE_LXML, reason="lxml required for XML repair")
def test_repair_refuses_error_formula_downgrade(tmp_path):
    src = tmp_path / "report.xlsx"
    _make_xlsx_with_error_formula(src)
    src_bytes = src.read_bytes()
    dest = tmp_path / "report_v002.xlsx"

    result = repair_workbook(src, dest)

    # REFUSAL, not downgrade: no output, no promotion, a defect receipt.
    assert result.output is None
    assert result.repaired is False
    assert result.promoted is False
    assert result.defect_code == "ERROR_FORMULA_DOWNGRADE_REFUSED"
    assert not result.fixes
    assert not dest.exists()
    # Zero-Destruction: the source (and its plat) is byte-identical.
    assert src.read_bytes() == src_bytes
    with zipfile.ZipFile(src) as zf:
        assert zf.read("xl/media/plat1.png") == b"\x89PNG\r\n\x1a\nFAKEPLATDATA"
        assert b"#REF!" in zf.read("xl/worksheets/sheet1.xml")
```

The old assertions `assert result.repaired` and
`assert any("errored formula" in f for f in result.fixes)` must not come
back in any form. Any assertion that a repair "succeeded" on an error
formula is the regression.

## Not covered by the patch (reviewer judgement; no packet test depends on these)

* **Trusted CORS preflight is blocked by auth.** The auth middleware is
  outermost, so `OPTIONS` preflights, which never carry credentials, return
  401 before `CORSMiddleware` sees them. That is safe but breaks legitimate
  cross-origin clients. If wanted, let requests with `method == "OPTIONS"`
  and an `access-control-request-method` header fall through.
  `CORSMiddleware` answers them itself and returns 400 without ACAO for
  untrusted origins. `test_untrusted_preflight_is_not_approved` still holds.
* **Token compare is not constant-time** (`==` in `security_controls.authorized`).
  Use `hmac.compare_digest`.
* **Negated recording labels.** `not recorded 2019-…` still matches
  `recorded`. The word boundary only closes the `unrecorded` substring case.
* **Two different complete schedules in one tract** are still summed
  together. Exact duplicates are now deduped, but a superseding schedule
  would still produce a 2.0. Per-document sum-to-one would close that. No
  test in this packet asserts either way.
* **`backend/=0.20.0`, `backend/=1.54.0`, …** are empty files committed at
  `582d951`. They are left over from an unquoted `pip install pkg>=x`.
  Delete them.
