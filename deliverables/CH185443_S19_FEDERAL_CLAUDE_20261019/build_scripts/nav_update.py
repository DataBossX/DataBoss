#!/usr/bin/env python3
"""Fold FEDERAL_NAVIGATION_OCR_ONLY.json (a locator index, no page text) into the page ledger and blocker register."""
import csv, json, sys
nav_path, d = sys.argv[1], sys.argv[2]
MAP = {f"WYW-{c} Part {p} of 4": f"F{c}P{p}" for c in ("131225", "133620") for p in (1, 2, 3)}
nav = {(MAP[r["source"]], r["page"]): r["hits"] for r in json.load(open(nav_path))}

rows = list(csv.DictReader(open(f"{d}/Page_Review_Ledger.csv")))
fields = list(rows[0].keys())
listed = unlisted = 0
for r in rows:
    if r["visual_status"] != "NOT_REVIEWABLE_IN_THIS_ENVIRONMENT":
        continue
    key = (r["source_id"], int(r["physical_page"]))
    if key in nav:
        listed += 1
        hits = ",".join(nav[key]) or "none"
        r["ocr_status"] = "ocr_text_listed_in_nav_index_offline_only"
        r["finding"] += f" LOCATOR HINT ONLY (OCR keyword flags from FEDERAL_NAVIGATION_OCR_ONLY.json, not source evidence): {hits}."
    else:
        unlisted += 1
        r["ocr_status"] = "ocr_claimed_by_register_but_no_text_located"
with open(f"{d}/Page_Review_Ledger.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
print("listed in nav:", listed, "| not listed:", unlisted, "| sum:", listed + unlisted)

blk = list(csv.DictReader(open(f"{d}/Missing_Source_and_Conflict_Register.csv")))
bf = list(blk[0].keys())
for r in blk:
    if r["issue_id"] == "B01":
        r["observed_conflict"] += (" The navigation index lists 1,098 of the 1,315 federal pages (WYW-131225 Parts 1-3, "
            "WYW-133620 Parts 1-3) as a locator only: it holds per-page keyword flags and an offline path, never page text.")
blk.append(dict(zip(bf, ["B10", "19", "WYW-094605 Part 1, 211 pages including CA WYW136880 agreement p.82 and approval p.81",
    "OCR text or page images for WYW-094605 Part 1",
    "FEDERAL_NAVIGATION_OCR_ONLY.json does not list WYW-094605 at all. The 15-source register claims a tesseract pass, but no text for these pages was located anywhere readable.",
    "B03 (approval date of CA WYW136880) depends on p.81 of this part, so it cannot be resolved without it.",
    "source_coverage_gate", "Ryan / Root (RyansPC)", "No cost; locate or regenerate the OCR, or export page images.", "OPEN"])))
blk.append(dict(zip(bf, ["B11", "19", "Keyword triage of federal pages",
    "A Section 19 locator term or a full-text index",
    "The index vocabulary has 10 terms. It includes section7 and section18 but no section19, and its broadest flags (depth 470 pages, approval 415) are too common to narrow anything.",
    "Section 19 pages cannot be found by keyword from this index, so any triage by it would be a guess.",
    "source_coverage_gate", "Federal source examiner", "No cost once OCR text is available.", "OPEN"])))
with open(f"{d}/Missing_Source_and_Conflict_Register.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=bf); w.writeheader(); w.writerows(blk)
print("blockers:", len(blk))
