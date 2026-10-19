"""Complete physical-page census keyed by content SHA-256 and physical page.

Every readable PDF page is included, including pages with native text. Boundary
signals are routing hints only. Imported visual receipts are assertions from
their named reviewers; this module does not run OCR, call models, or inspect pixels.
"""
from __future__ import annotations
import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict

FIELDS = ["pdf", "page", "reason", "source_sha256", "page_id", "source_paths",
          "candidate_signals", "status", "review_method", "reviewer",
          "reviewed_at", "evidence_ref", "disposition", "review_origin"]
REVIEW_FIELDS = ["review_method", "reviewer", "reviewed_at", "evidence_ref",
                 "disposition"]
VISUAL_METHODS = {"HUMAN_VISION", "MODEL_VISION", "INHERITED_VISION"}
SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def positive_integer(value):
    text = str(value or "")
    if not re.fullmatch(r"[1-9][0-9]*", text):
        raise ValueError("expected a positive integer: %r" % value)
    return int(text)


def visual_receipt_valid(row):
    return (row.get("status") == "VISUALLY_REVIEWED"
            and row.get("review_method") in VISUAL_METHODS
            and all(str(row.get(key) or "").strip()
                    for key in ("reviewer", "reviewed_at", "evidence_ref")))


def build_queue(inventory_csv, boundaries_csv, review_csv=None, issues=None):
    """Return one row for each distinct SHA/page, retaining all path aliases.

    If issues is supplied it is populated with omissions/ambiguous hints.
    Without that explicit channel, invalid source measurements raise ValueError
    rather than making an incomplete page census appear complete.
    """
    local_issues = []
    bodies = {}
    by_name = defaultdict(set)
    with open(inventory_csv, newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if row.get("ext", "").lower() != ".pdf":
                continue
            sha = row.get("sha256", "").lower()
            path = row.get("path") or row.get("name") or ""
            try:
                pages = positive_integer(row.get("pages"))
                if row.get("error") or not SHA_RE.fullmatch(sha) or not path:
                    raise ValueError("invalid hash, missing path, or extraction error")
            except ValueError as exc:
                local_issues.append({"code": "UNMEASURED_PDF", "path": path,
                                     "detail": str(row.get("error") or exc)})
                continue
            info = bodies.setdefault(sha, {"pages": pages, "paths": set(),
                                           "names": set()})
            if info["pages"] != pages:
                raise ValueError("conflicting page counts for content hash " + sha)
            info["paths"].add(path)
            name = row.get("name") or os.path.basename(path)
            info["names"].add(name)
            by_name[name].add(sha)

    hints = defaultdict(set)
    with open(boundaries_csv, newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if not row.get("page"):
                continue
            pdf = row.get("pdf", "")
            hashes = by_name.get(pdf, set())
            try:
                page = positive_integer(row["page"])
            except ValueError:
                local_issues.append({"code": "INVALID_BOUNDARY_PAGE",
                                     "path": pdf, "detail": row.get("page", "")})
                continue
            if len(hashes) != 1:
                local_issues.append({"code": "AMBIGUOUS_BOUNDARY_BASENAME",
                                     "path": pdf,
                                     "detail": "hint ignored; matching bodies=%d" % len(hashes)})
                continue
            sha = next(iter(hashes))
            if page > bodies[sha]["pages"]:
                local_issues.append({"code": "BOUNDARY_OUT_OF_RANGE", "path": pdf,
                                     "detail": str(page)})
                continue
            signal = row.get("signal", "").strip()
            if signal:
                hints[(sha, page)].add(signal)

    reviewed = {}
    if review_csv:
        with open(review_csv, newline="", encoding="utf-8") as stream:
            for row in csv.DictReader(stream):
                sha = row.get("source_sha256", "").lower()
                try:
                    page = positive_integer(row.get("page"))
                except ValueError:
                    continue
                if sha not in bodies or page > bodies[sha]["pages"]:
                    local_issues.append({"code": "STALE_REVIEW_RECEIPT",
                                         "path": sha, "detail": str(page)})
                    continue
                if visual_receipt_valid(row):
                    key = (sha, page)
                    if key in reviewed and any(reviewed[key].get(k) != row.get(k)
                                                for k in REVIEW_FIELDS):
                        raise ValueError("conflicting visual receipts for %s:%s" % key)
                    reviewed[key] = row

    fatal = [r for r in local_issues if r["code"] == "UNMEASURED_PDF"]
    if issues is not None:
        issues.extend(local_issues)
    elif fatal:
        raise ValueError("page census is incomplete: " + json.dumps(fatal))

    queue = []
    for sha, info in sorted(bodies.items(), key=lambda pair: (min(pair[1]["paths"]), pair[0])):
        for page in range(1, info["pages"] + 1):
            key = (sha, page)
            result = dict.fromkeys(FIELDS, "")
            result.update(pdf=min(info["names"]), page=page,
                          reason="EVERY_PHYSICAL_PAGE_REQUIRES_VISUAL_ACCOUNTING",
                          source_sha256=sha, page_id="%s:%s" % key,
                          source_paths=json.dumps(sorted(info["paths"])),
                          candidate_signals=json.dumps(sorted(hints[key])),
                          status="UNREVIEWED")
            if key in reviewed:
                result.update({k: reviewed[key].get(k, "") for k in REVIEW_FIELDS})
                result.update(status="VISUALLY_REVIEWED", review_origin="IMPORTED_RECEIPT")
            queue.append(result)
    return queue


def main(argv=None):
    parser = argparse.ArgumentParser(prog="peaches.vision_queue")
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--boundaries", required=True)
    parser.add_argument("--reviews")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    issues = []
    queue = build_queue(args.inventory, args.boundaries, args.reviews, issues)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    # Exclusive output creation prevents silently replacing a worker's ledger.
    with open(args.out, "x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(queue)
    with open(str(args.out) + ".issues.json", "x", encoding="utf-8") as stream:
        json.dump(issues, stream, indent=2)
    reviewed = sum(visual_receipt_valid(row) for row in queue)
    print("page census: %d pages; %d imported visual receipts; %d pending; %d issues"
          % (len(queue), reviewed, len(queue) - reviewed, len(issues)))
    return 1 if any(r["code"] == "UNMEASURED_PDF" for r in issues) else 0


if __name__ == "__main__":
    sys.exit(main())
