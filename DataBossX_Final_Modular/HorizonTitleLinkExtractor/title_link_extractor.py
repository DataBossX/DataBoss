"""
title_link_extractor.py
=======================
Main orchestrator for HorizonTitleLinkExtractor.

Pipeline (REVIEW ONLY by default):
  1. Load config + .env, run the Drive security/permission check.
  2. Select + download the source workbook (Drive Mode A/B or local input/).
  3. Open a non-destructive review copy of the workbook.
  4. For each title/runsheet worksheet: detect header + columns.
  5. For each row with a document hyperlink:
       open preview -> click View -> capture document image(s) in memory ->
       run AI vision extraction + consensus -> compare to row -> write review
       columns + color code.
  6. Log every row (run_log.csv), accumulate summary.csv, errors.log.
  7. Save the review workbook and upload outputs back to Drive (or print manual
     instructions).

CLI:
  python title_link_extractor.py --login-setup
  python title_link_extractor.py --test           # only test_mode_rows linked rows
  python title_link_extractor.py --run            # full configured job
  python title_link_extractor.py --upload-only    # upload latest output to Drive
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import glob
import logging
import os
import sys
import time
from typing import Any

from dotenv import load_dotenv

import config_schema
import drive_sync
import excel_writer as xl
import report as report_mod
from ai_extractors import MAJOR_FIELDS, ModelRouter
from browser_viewer import BrowserViewer, LoginExpiredError, run_login_setup
from cache import CostTracker, ResultCache

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.yaml")

INPUT_DIR = os.path.join(HERE, "input")
OUTPUT_DIR = os.path.join(HERE, "output")
LOGS_DIR = os.path.join(HERE, "logs")
TEMP_DIR = os.path.join(HERE, "temp")
DEBUG_DIR = os.path.join(HERE, "debug")

RUN_LOG = os.path.join(LOGS_DIR, "run_log.csv")
SUMMARY_LOG = os.path.join(LOGS_DIR, "summary.csv")
ERRORS_LOG = os.path.join(LOGS_DIR, "errors.log")

RUN_LOG_HEADER = ["timestamp", "workbook", "sheet", "row", "link", "status",
                  "confidence", "changed_fields", "review_needed", "error_message"]

log = logging.getLogger("horizon")


# =============================================================================
# Setup helpers
# =============================================================================
def ensure_dirs() -> None:
    for d in (INPUT_DIR, OUTPUT_DIR, LOGS_DIR, TEMP_DIR, DEBUG_DIR,
              os.path.join(HERE, ".auth")):
        os.makedirs(d, exist_ok=True)


def load_config() -> dict[str, Any]:
    cfg = config_schema.load_validated(CONFIG_PATH)  # validates + applies defaults
    cfg.setdefault("input_dir", INPUT_DIR)
    cfg.setdefault("debug_dir", DEBUG_DIR)
    return cfg


def setup_logging() -> None:
    os.makedirs(LOGS_DIR, exist_ok=True)
    root = logging.getLogger("horizon")
    root.setLevel(logging.INFO)
    root.handlers.clear()

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(console)

    errfile = logging.FileHandler(ERRORS_LOG, encoding="utf-8")
    errfile.setLevel(logging.WARNING)
    errfile.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root.addHandler(errfile)


def init_run_log() -> None:
    if not os.path.exists(RUN_LOG):
        with open(RUN_LOG, "w", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerow(RUN_LOG_HEADER)


def append_run_log(row: list[Any]) -> None:
    with open(RUN_LOG, "a", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerow(row)


def completed_keys() -> set[str]:
    """Return {sheet|row} keys already completed (status not failed) for resume."""
    done: set[str] = set()
    if not os.path.exists(RUN_LOG):
        return done
    try:
        with open(RUN_LOG, "r", encoding="utf-8") as fh:
            for rec in csv.DictReader(fh):
                status = (rec.get("status") or "").lower()
                if status and status not in ("failed", "error", "login_expired"):
                    done.add(f"{rec.get('sheet')}|{rec.get('row')}")
    except Exception:
        pass
    return done


# =============================================================================
# Per-row processing
# =============================================================================
def _color_for(status: str, confidence: float, changed: list[str],
               review_needed: bool, cfg: dict[str, Any]) -> str:
    if status in ("failed", "login_expired", "blocked", "unreadable"):
        return "red"
    if confidence < float(cfg.get("ai_confidence_review_threshold", 0.85)):
        return "red"
    if changed or review_needed:
        return "yellow"
    if confidence >= float(cfg.get("ai_confidence_auto_safe_threshold", 0.97)):
        return "green"
    return "yellow"


def process_row(link_row: xl.LinkRow, layout: xl.SheetLayout, viewer: BrowserViewer,
                router: ModelRouter, cfg: dict[str, Any], workbook_name: str
                ) -> dict[str, Any]:
    """Process a single linked row. Returns a run-log-friendly dict; never raises
    except LoginExpiredError (which must stop the whole run)."""
    ts = _dt.datetime.now().isoformat(timespec="seconds")
    base = {"timestamp": ts, "workbook": workbook_name,
            "sheet": link_row.sheet_title, "row": link_row.row,
            "link": link_row.link}

    # --- capture (raises LoginExpiredError upward) -------------------------
    cap = viewer.capture_document(link_row.link, row_id=link_row.row)
    if not cap.get("ok"):
        status = "failed"
        err = cap.get("error") or "capture failed"
        result = {
            "status": status, "confidence": 0.0, "consensus_label": "",
            "suggestions": {}, "consensus_fields": [], "notes": "",
            "changed_fields": [], "error": err, "review_needed": True,
            "timestamp": ts, "source_link": link_row.link,
            "viewer_method": cap.get("viewer_method", ""),
            "model_used": "", "validator_models": [],
            "color": "red",
        }
        xl.write_review(layout, link_row.row, result)
        return {**base, "status": status, "confidence": 0.0,
                "changed_fields": "", "review_needed": True, "error_message": err,
                "color": "red", "consensus_label": "", "notes": err,
                "viewer_method": cap.get("viewer_method", "")}

    # --- AI extraction -----------------------------------------------------
    images = cap["images"]
    try:
        ai = router.extract(images, row_changed_hint=False, row_id=link_row.row)
    except Exception as exc:
        err = f"AI extraction failed: {type(exc).__name__}: {exc}"
        log.warning(err)
        result = {
            "status": "failed", "confidence": 0.0, "consensus_label": "",
            "suggestions": {}, "consensus_fields": [], "notes": "",
            "changed_fields": [], "error": err, "review_needed": True,
            "timestamp": ts, "source_link": link_row.link,
            "viewer_method": cap.get("viewer_method", ""),
            "model_used": cfg.get("openai_model", ""), "validator_models": [],
            "color": "red",
        }
        xl.write_review(layout, link_row.row, result)
        return {**base, "status": "failed", "confidence": 0.0,
                "changed_fields": "", "review_needed": True, "error_message": err,
                "color": "red", "consensus_label": "", "notes": err,
                "viewer_method": cap.get("viewer_method", "")}

    primary = ai["primary"]
    # Build the suggestion dict: consensus values win; else primary's reading.
    suggestions = {f: getattr(primary, f) for f in MAJOR_FIELDS}
    suggestions.update(ai["consensus"])

    changed, minor = xl.compare_fields(
        link_row.values, suggestions, MAJOR_FIELDS,
        same_threshold=float(cfg.get("match_same_threshold", 0.97)),
        minor_threshold=float(cfg.get("match_minor_threshold", 0.85)))
    # Disagreement among models -> keep original untouched, force review.
    disagree = ai["disagree_fields"]
    confidence = float(ai["confidence"])
    review_needed = bool(ai["needs_human_review"] or disagree)

    if disagree:
        # Do not suggest values where validators disagreed.
        for fld in disagree:
            suggestions[fld] = None

    if changed and review_needed:
        status = "changed_review"
    elif changed:
        status = "changed"
    elif review_needed:
        status = "review"
    else:
        status = "ok"

    color = _color_for(status, confidence, changed, review_needed, cfg)
    if disagree or ai.get("poor_image"):
        color = "red" if ai.get("poor_image") else "yellow"

    consensus_label = (
        "consensus" if ai["consensus_fields"] else
        ("disagreement" if disagree else "single_model"))

    notes_parts = []
    if primary.evidence_summary:
        notes_parts.append(primary.evidence_summary)
    if primary.uncertain_fields:
        notes_parts.append("Uncertain: " + ", ".join(primary.uncertain_fields))
    if minor:
        notes_parts.append("Minor diffs (formatting): " + ", ".join(minor))
    if disagree:
        notes_parts.append("Model disagreement: " + ", ".join(disagree))
    if ai.get("poor_image"):
        notes_parts.append(
            f"Poor image quality (score={ai.get('image_quality')})")
    notes = " | ".join(notes_parts)

    result = {
        "status": status, "confidence": confidence,
        "consensus_label": consensus_label, "suggestions": suggestions,
        "consensus_fields": ai["consensus_fields"], "notes": notes,
        "changed_fields": changed, "error": "", "review_needed": review_needed,
        "timestamp": ts, "source_link": link_row.link,
        "viewer_method": cap.get("viewer_method", ""),
        "model_used": ai["models_used"],
        "validator_models": ai["validator_models_used"],
        "color": color,
    }
    xl.write_review(layout, link_row.row, result)

    # Optional destructive apply (disabled by default).
    if cfg.get("apply_corrections") and changed and not disagree:
        only_consensus = [f for f in changed if f in set(ai["consensus_fields"])]
        if only_consensus:
            xl.apply_corrections(layout, link_row.row, suggestions, only_consensus,
                                 highlight=bool(cfg.get("highlight_changed_cells")))

    return {**base, "status": status, "confidence": round(confidence, 3),
            "changed_fields": ", ".join(changed), "review_needed": review_needed,
            "error_message": "", "color": color,
            "consensus_label": consensus_label, "notes": notes,
            "viewer_method": cap.get("viewer_method", "")}


def _wipe_temp(cfg: dict[str, Any]) -> None:
    if not cfg.get("delete_temp_after_each_row", True):
        return
    if cfg.get("debug_save_screenshots"):
        return
    for f in glob.glob(os.path.join(TEMP_DIR, "*")):
        try:
            os.remove(f)
        except OSError:
            pass


# =============================================================================
# Job runner
# =============================================================================
def run_job(test_mode: bool) -> int:
    ensure_dirs()
    setup_logging()
    init_run_log()
    load_dotenv(os.path.join(HERE, ".env"))
    cfg = load_config()
    cfg["debug_dir"] = DEBUG_DIR

    start_time = _dt.datetime.now()
    summary = {k: 0 for k in (
        "total_rows_seen", "linked_rows", "processed_rows", "skipped_rows",
        "failed_rows", "changed_rows", "high_confidence_rows", "review_needed_rows")}

    # --- 1. Drive security check ------------------------------------------
    drive = drive_sync.DriveSync.create(cfg)
    perm = drive.check_permissions()
    log.info("=" * 70)
    log.info(" SECURITY / DRIVE CHECK")
    log.info(" %s", perm["message"])
    if perm.get("public_writer"):
        log.warning(" >>> Lock down the Drive folder before continuing. <<<")
    log.info("=" * 70)

    if not os.getenv("OPENAI_API_KEY"):
        log.error("OPENAI_API_KEY is not set in .env. Cannot run AI extraction.")
        return 2

    auth_path = os.path.join(HERE, cfg.get("auth_state_path", ".auth/county_state.json"))
    if not os.path.exists(auth_path):
        log.warning("No county auth state at %s. Run RUN_LOGIN_SETUP.bat first if "
                    "the county site requires login.", auth_path)

    # --- 2. source workbook -----------------------------------------------
    try:
        source_path = drive.download_source(INPUT_DIR)
    except Exception as exc:
        log.error("Could not obtain source workbook: %s", exc)
        return 3
    log.info("Source workbook: %s", source_path)

    # --- 3. review copy ---------------------------------------------------
    wb, review_path = xl.load_workbook_copy(source_path, OUTPUT_DIR)
    workbook_name = os.path.basename(review_path)

    sheets = xl.detect_title_sheets(wb)
    if not sheets:
        log.error("No title/runsheet worksheets detected in the workbook.")
        return 4
    log.info("Detected %d title sheet(s): %s",
             len(sheets), ", ".join(s.title for s in sheets))

    cost = CostTracker()
    rcache = ResultCache(os.path.join(HERE, cfg.get("cache_dir", ".cache")),
                         enabled=bool(cfg.get("use_cache", True)))
    router = ModelRouter(cfg, cost=cost, result_cache=rcache)
    report_rows: list[dict[str, Any]] = []
    done_keys = (completed_keys()
                 if cfg.get("resume_from_log") and not cfg.get("force_reprocess")
                 else set())

    test_limit = int(cfg.get("test_mode_rows", 5)) if test_mode else None
    max_rows = cfg.get("max_rows")
    start_row = cfg.get("start_row")
    end_row = cfg.get("end_row")
    delay = float(cfg.get("request_delay_seconds", 1.0))
    processed_count = 0
    stop_all = False

    # --- 4/5. iterate ------------------------------------------------------
    try:
        with BrowserViewer(cfg) as viewer:
            for ws in sheets:
                if stop_all:
                    break
                layout = xl.detect_header(ws)
                if not layout:
                    continue
                xl.ensure_review_columns(layout)

                for skipped_r in xl.rows_without_links(layout):
                    summary["total_rows_seen"] += 1
                    summary["skipped_rows"] += 1
                    append_run_log([_dt.datetime.now().isoformat(timespec="seconds"),
                                    workbook_name, ws.title, skipped_r, "", "skipped",
                                    "", "", "", "no usable link"])

                for link_row in xl.iter_link_rows(layout):
                    summary["total_rows_seen"] += 1
                    summary["linked_rows"] += 1

                    if start_row and link_row.row < int(start_row):
                        continue
                    if end_row and link_row.row > int(end_row):
                        continue

                    key = f"{ws.title}|{link_row.row}"
                    if key in done_keys:
                        log.info("Resume: skipping already-done %s", key)
                        continue

                    if test_limit is not None and processed_count >= test_limit:
                        stop_all = True
                        break
                    if max_rows and processed_count >= int(max_rows):
                        stop_all = True
                        break

                    log.info("Processing %s row %d -> %s",
                             ws.title, link_row.row, link_row.link[:80])
                    attempts = int(cfg.get("max_retries_per_row", 3))
                    rec = None
                    for attempt in range(1, attempts + 1):
                        try:
                            rec = process_row(link_row, layout, viewer, router,
                                               cfg, workbook_name)
                            break
                        except LoginExpiredError as exc:
                            log.error("LOGIN EXPIRED: %s", exc)
                            append_run_log([
                                _dt.datetime.now().isoformat(timespec="seconds"),
                                workbook_name, ws.title, link_row.row, link_row.link,
                                "login_expired", "", "", "YES", str(exc)])
                            stop_all = True
                            rec = None
                            break
                        except Exception as exc:  # continue after failures
                            log.warning("Row %d attempt %d failed: %s",
                                        link_row.row, attempt, exc)
                            if attempt == attempts:
                                rec = {"timestamp":
                                       _dt.datetime.now().isoformat(timespec="seconds"),
                                       "workbook": workbook_name, "sheet": ws.title,
                                       "row": link_row.row, "link": link_row.link,
                                       "status": "failed", "confidence": 0.0,
                                       "changed_fields": "", "review_needed": True,
                                       "error_message": str(exc)}
                            else:
                                time.sleep(2 ** attempt)

                    if stop_all and rec is None:
                        break
                    if rec is None:
                        continue

                    append_run_log([rec["timestamp"], rec["workbook"], rec["sheet"],
                                    rec["row"], rec["link"], rec["status"],
                                    rec["confidence"], rec["changed_fields"],
                                    "YES" if rec["review_needed"] else "no",
                                    rec["error_message"]])

                    report_rows.append({
                        "sheet": rec["sheet"], "row": rec["row"],
                        "status": rec["status"], "confidence": rec["confidence"],
                        "consensus_label": rec.get("consensus_label", ""),
                        "changed_fields": (rec["changed_fields"].split(", ")
                                           if rec["changed_fields"] else []),
                        "review_needed": rec["review_needed"],
                        "viewer_method": rec.get("viewer_method", ""),
                        "notes": rec.get("notes", ""),
                        "color": rec.get("color", ""), "link": rec["link"]})

                    # summary tallies
                    if rec["status"] in ("failed", "login_expired"):
                        summary["failed_rows"] += 1
                    else:
                        summary["processed_rows"] += 1
                    if rec["changed_fields"]:
                        summary["changed_rows"] += 1
                    if rec["review_needed"]:
                        summary["review_needed_rows"] += 1
                    if isinstance(rec["confidence"], (int, float)) and \
                            rec["confidence"] >= float(
                                cfg.get("ai_confidence_auto_safe_threshold", 0.97)):
                        summary["high_confidence_rows"] += 1

                    processed_count += 1
                    _wipe_temp(cfg)
                    time.sleep(delay)
    finally:
        wb.save(review_path)
        log.info("Saved review workbook: %s", review_path)

    # --- 6. summary + cost + HTML report -----------------------------------
    end_time = _dt.datetime.now()
    _write_summary(summary, start_time, end_time)

    cost_csv = os.path.join(LOGS_DIR, "cost.csv")
    try:
        cost.write_csv(cost_csv)
        log.info("Estimated AI cost this run: $%.4f (%d billable calls)",
                 cost.total_usd, cost.total_calls)
    except Exception as exc:
        log.warning("Could not write cost log: %s", exc)

    report_path = None
    if cfg.get("generate_html_report", True):
        try:
            report_path = os.path.join(
                OUTPUT_DIR, os.path.splitext(workbook_name)[0] + "_REPORT.html")
            report_mod.build_report(
                report_path, workbook_name,
                end_time.isoformat(timespec="seconds"), summary, report_rows,
                total_cost=cost.total_usd)
            log.info("HTML report: %s", report_path)
        except Exception as exc:
            log.warning("Could not build HTML report: %s", exc)
            report_path = None

    # --- 7. upload ---------------------------------------------------------
    summary_csv = SUMMARY_LOG
    uploaded = None
    upload_files = [review_path, RUN_LOG, summary_csv, cost_csv]
    if report_path:
        upload_files.append(report_path)
    try:
        uploaded = drive.upload_outputs([f for f in upload_files
                                         if f and os.path.exists(f)])
    except Exception as exc:
        log.warning("Drive upload failed: %s", exc)

    log.info("=" * 70)
    log.info(" DONE.")
    log.info(" Review workbook : %s", review_path)
    log.info(" Run log         : %s", RUN_LOG)
    log.info(" Summary         : %s", summary_csv)
    if uploaded:
        log.info(" Drive output    : %s", uploaded)
    else:
        log.info(" Drive upload    : not configured (see instructions above).")
    log.info(" Rows linked=%d processed=%d skipped=%d failed=%d changed=%d "
             "review=%d", summary["linked_rows"], summary["processed_rows"],
             summary["skipped_rows"], summary["failed_rows"],
             summary["changed_rows"], summary["review_needed_rows"])
    log.info("=" * 70)
    return 0


def _write_summary(summary: dict[str, int], start: _dt.datetime,
                   end: _dt.datetime) -> None:
    summary = dict(summary)
    summary["start_time"] = start.isoformat(timespec="seconds")
    summary["end_time"] = end.isoformat(timespec="seconds")
    with open(SUMMARY_LOG, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        for k, v in summary.items():
            w.writerow([k, v])


def upload_only() -> int:
    ensure_dirs()
    setup_logging()
    load_dotenv(os.path.join(HERE, ".env"))
    cfg = load_config()
    reviews = sorted(glob.glob(os.path.join(OUTPUT_DIR, "*_AI_REVIEW_*.xlsx")),
                     key=os.path.getmtime, reverse=True)
    if not reviews:
        log.error("No review workbook found in output/. Run a review first.")
        return 1
    latest = reviews[0]
    log.info("Uploading latest review workbook: %s", latest)
    drive = drive_sync.DriveSync.create(cfg)
    files = [latest]
    if os.path.exists(RUN_LOG):
        files.append(RUN_LOG)
    if os.path.exists(SUMMARY_LOG):
        files.append(SUMMARY_LOG)
    url = drive.upload_outputs(files)
    if url:
        log.info("Uploaded to: %s", url)
    return 0


# =============================================================================
# Doctor / preflight
# =============================================================================
def doctor() -> int:
    """Preflight checklist: dependencies, keys, auth, drive, config."""
    ensure_dirs()
    setup_logging()
    load_dotenv(os.path.join(HERE, ".env"))
    ok = True

    def check(label: str, passed: bool, warn: bool = False, hint: str = "") -> None:
        nonlocal ok
        mark = "PASS" if passed else ("WARN" if warn else "FAIL")
        if not passed and not warn:
            ok = False
        line = f" [{mark}] {label}"
        if hint and not passed:
            line += f"\n         -> {hint}"
        log.info(line)

    log.info("=" * 70)
    log.info(" HORIZON TITLE EXTRACTOR - DOCTOR")
    log.info("=" * 70)

    check(f"Python {sys.version_info.major}.{sys.version_info.minor} (need 3.11+)",
          sys.version_info >= (3, 11), hint="Install Python 3.11 or newer.")

    deps = ["openpyxl", "yaml", "pydantic", "tenacity", "dotenv", "PIL",
            "playwright", "openai"]
    for mod in deps:
        try:
            __import__(mod)
            check(f"dependency: {mod}", True)
        except Exception:
            check(f"dependency: {mod}", False,
                  hint="Run INSTALL.bat to install requirements.")

    # config validity
    try:
        cfg = load_config()
        check("config.yaml is valid", True)
    except Exception as exc:
        check("config.yaml is valid", False, hint=str(exc))
        cfg = {}

    # .env / keys
    env_path = os.path.join(HERE, ".env")
    check(".env file present", os.path.exists(env_path),
          hint="Copy .env.example to .env and add your keys.")
    check("OPENAI_API_KEY set (primary extractor)", bool(os.getenv("OPENAI_API_KEY")),
          hint="Add OPENAI_API_KEY to .env.")
    check("GEMINI_API_KEY set (optional validator)", bool(os.getenv("GEMINI_API_KEY")),
          warn=True, hint="Optional second opinion.")
    check("ANTHROPIC_API_KEY set (optional validator)",
          bool(os.getenv("ANTHROPIC_API_KEY")), warn=True,
          hint="Optional second opinion.")

    # auth state
    auth = os.path.join(HERE, cfg.get("auth_state_path", ".auth/county_state.json"))
    check("county login state saved", os.path.exists(auth), warn=True,
          hint="Run RUN_LOGIN_SETUP.bat if county records need login.")

    # drive + security
    try:
        drive = drive_sync.DriveSync.create(cfg)
        perm = drive.check_permissions()
        check(f"Drive: {perm['message']}", not perm.get("public_writer"),
              warn=not perm.get("public_writer") and not perm.get("configured"),
              hint="Lock the Drive folder to Restricted/Viewer-only.")
    except Exception as exc:
        check("Drive configuration", False, warn=True, hint=str(exc))

    log.info("=" * 70)
    log.info(" RESULT: %s", "READY" if ok else "NOT READY (fix FAIL items above)")
    log.info("=" * 70)
    return 0 if ok else 1


# =============================================================================
# CLI
# =============================================================================
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="HorizonTitleLinkExtractor")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--login-setup", action="store_true",
                       help="Open a browser to log into county records and save state.")
    group.add_argument("--doctor", action="store_true",
                       help="Run a preflight checklist of deps, keys, auth, drive.")
    group.add_argument("--test", action="store_true",
                       help="Process only test_mode_rows linked rows.")
    group.add_argument("--run", action="store_true",
                       help="Run the full configured review job.")
    group.add_argument("--upload-only", action="store_true",
                       help="Upload the latest output to Drive.")
    args = parser.parse_args(argv)

    ensure_dirs()
    if args.doctor:
        return doctor()
    if args.login_setup:
        setup_logging()
        cfg = load_config()
        auth = os.path.join(HERE, cfg.get("auth_state_path",
                                          ".auth/county_state.json"))
        run_login_setup(auth)
        return 0
    if args.upload_only:
        return upload_only()
    return run_job(test_mode=args.test)


if __name__ == "__main__":
    sys.exit(main())
