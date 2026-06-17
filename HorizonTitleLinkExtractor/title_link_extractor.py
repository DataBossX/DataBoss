"""
title_link_extractor.py
========================
Main orchestrator for HorizonTitleLinkExtractor.

Modes (chosen by RUN_*.bat via CLI flags):
  --login-setup   Open a browser so the user can log into county records.
  --test          Process only `test_mode_rows` linked rows (default 5).
  --full          Process the whole workbook per config.
  --upload-only   Upload the latest local output to Google Drive.

Pipeline (per row with a document link):
  Drive -> download workbook -> read rows -> open link in Playwright ->
  click View -> capture document image(s) in memory -> AI vision extraction
  -> consensus -> compare to row -> write review columns -> log -> continue.

DEFAULT MODE IS REVIEW ONLY. The original workbook is never overwritten.
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import shutil
import sys
from datetime import datetime
from typing import Dict, List, Optional

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# Bootstrapping: config, env, logging
# ---------------------------------------------------------------------------


def load_config() -> dict:
    path = os.path.join(HERE, "config.yaml")
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_env() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(os.path.join(HERE, ".env"))
    except Exception:
        pass


def setup_logging() -> logging.Logger:
    logs_dir = os.path.join(HERE, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    logger = logging.getLogger("horizon")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(console)

    errfile = logging.FileHandler(os.path.join(logs_dir, "errors.log"), encoding="utf-8")
    errfile.setLevel(logging.WARNING)
    errfile.setFormatter(fmt)
    logger.addHandler(errfile)

    return logger


log = logging.getLogger("horizon")


# ---------------------------------------------------------------------------
# CSV audit logs
# ---------------------------------------------------------------------------

RUN_LOG_HEADERS = [
    "timestamp", "workbook", "sheet", "row", "link", "status",
    "confidence", "changed_fields", "review_needed", "error_message",
]


class AuditLog:
    def __init__(self, logs_dir: str):
        self.logs_dir = logs_dir
        self.run_log_path = os.path.join(logs_dir, "run_log.csv")
        self.summary_path = os.path.join(logs_dir, "summary.csv")
        self._completed: set = set()  # (workbook, sheet, row) already done
        self._ensure_run_log()

    def _ensure_run_log(self) -> None:
        if not os.path.exists(self.run_log_path):
            with open(self.run_log_path, "w", newline="", encoding="utf-8") as fh:
                csv.writer(fh).writerow(RUN_LOG_HEADERS)

    def load_completed(self) -> None:
        """Read existing run_log.csv to support resume_from_log."""
        if not os.path.exists(self.run_log_path):
            return
        try:
            with open(self.run_log_path, "r", newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                for r in reader:
                    if r.get("status") in ("processed", "skipped", "green", "yellow"):
                        self._completed.add(
                            (r.get("workbook"), r.get("sheet"), str(r.get("row")))
                        )
        except Exception as exc:
            log.warning("Could not read run_log for resume: %s", exc)

    def already_done(self, workbook: str, sheet: str, row: int) -> bool:
        return (workbook, sheet, str(row)) in self._completed

    def write_row(self, **kw) -> None:
        with open(self.run_log_path, "a", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerow([kw.get(h, "") for h in RUN_LOG_HEADERS])

    def write_summary(self, stats: Dict) -> None:
        with open(self.summary_path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            for k, v in stats.items():
                w.writerow([k, v])


# ---------------------------------------------------------------------------
# Output workbook naming (never overwrite the original)
# ---------------------------------------------------------------------------


def make_output_path(source_path: str, output_dir: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(source_path))[0]
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    return os.path.join(output_dir, f"{base}__AI_REVIEW_{stamp}.xlsx")


# ---------------------------------------------------------------------------
# The processing job
# ---------------------------------------------------------------------------


class Job:
    def __init__(self, config: dict, mode: str):
        self.config = config
        self.mode = mode  # "test" or "full"
        self.logs_dir = os.path.join(HERE, "logs")
        self.input_dir = os.path.join(HERE, "input")
        self.output_dir = os.path.join(HERE, "output")
        self.temp_dir = os.path.join(HERE, "temp")
        for d in (self.logs_dir, self.input_dir, self.output_dir, self.temp_dir):
            os.makedirs(d, exist_ok=True)
        self.audit = AuditLog(self.logs_dir)
        self.stats = {
            "total_rows_seen": 0,
            "linked_rows": 0,
            "processed_rows": 0,
            "skipped_rows": 0,
            "failed_rows": 0,
            "changed_rows": 0,
            "high_confidence_rows": 0,
            "review_needed_rows": 0,
            "start_time": "",
            "end_time": "",
        }
        self.output_path: Optional[str] = None

    # -- main run ------------------------------------------------------------
    def run(self) -> int:
        import drive_sync
        import excel_writer
        from ai_extractors import ModelRouter
        from browser_viewer import BrowserViewer

        self.stats["start_time"] = datetime.now().isoformat(timespec="seconds")

        # 1. Drive backend + security check + workbook selection.
        backend = drive_sync.build_backend(self.config)
        warning = backend.security_check()
        if warning:
            print("\n" + "!" * 70)
            print(warning)
            print("!" * 70 + "\n")
            log.warning(warning)

        source_path = self._obtain_workbook(backend, drive_sync)
        if not source_path:
            log.error("No source workbook found. Aborting.")
            return 2
        print(f"\nSelected source workbook: {os.path.basename(source_path)}\n")

        # 2. Open output copy (never touch the original).
        self.output_path = make_output_path(source_path, self.output_dir)
        wb = excel_writer.load_workbook(source_path)

        # 3. AI router + browser.
        router = ModelRouter(self.config)
        print(f"AI models available: {router.available_summary()}")
        if not router.primary.available:
            log.error("OPENAI_API_KEY missing - primary extractor unavailable. Aborting.")
            return 3

        if self.config.get("resume_from_log", True) and not self.config.get("force_reprocess", False):
            self.audit.load_completed()

        with BrowserViewer(self.config) as viewer:
            if not viewer.login_valid():
                log.error(
                    "No county login session found (%s). Run RUN_LOGIN_SETUP.bat.",
                    self.config.get("auth_state_path"),
                )
                return 4
            stop = self._process_workbook(wb, viewer, router, excel_writer,
                                          os.path.basename(source_path))

        # 4. Save output workbook.
        wb.save(self.output_path)
        print(f"\nOutput workbook saved to:\n  {self.output_path}\n")

        # 5. Finalize logs + summary.
        self.stats["end_time"] = datetime.now().isoformat(timespec="seconds")
        self.audit.write_summary(self.stats)
        self._print_summary()

        # 6. Upload (or print manual instructions).
        self._deliver(backend)

        if stop:
            print("\n[NOTICE] Run stopped early because the county login expired.")
            print("Please rerun RUN_LOGIN_SETUP.bat and run again.\n")
        return 0

    # -- workbook acquisition ------------------------------------------------
    def _obtain_workbook(self, backend, drive_sync) -> Optional[str]:
        candidates = []
        try:
            candidates = backend.list_candidates()
        except Exception as exc:
            log.error("Could not list Drive candidates: %s", exc)

        if candidates:
            chosen = drive_sync.select_workbook(
                candidates, self.config.get("source_workbook_name_override")
            )
            if chosen:
                try:
                    return backend.download(chosen, self.input_dir)
                except Exception as exc:
                    log.error("Download failed: %s", exc)

        # Fallback: use any .xlsx already sitting in input/.
        for name in os.listdir(self.input_dir):
            if name.lower().endswith((".xlsx", ".xlsm")) and "AI_REVIEW" not in name:
                log.warning("Using local fallback workbook from input/: %s", name)
                return os.path.join(self.input_dir, name)
        return None

    # -- per-workbook loop ---------------------------------------------------
    def _process_workbook(self, wb, viewer, router, excel_writer, workbook_name) -> bool:
        """Process every title sheet. Returns True if stopped (login expired)."""
        max_test = int(self.config.get("test_mode_rows", 5))
        start_row = self.config.get("start_row")
        end_row = self.config.get("end_row")
        max_rows = self.config.get("max_rows")
        delay = float(self.config.get("request_delay_seconds", 1.0))
        safe_thr = float(self.config.get("ai_confidence_auto_safe_threshold", 0.97))
        processed_links = 0
        import time

        for ws in wb.worksheets:
            sheet = excel_writer.detect_header(ws)
            if not sheet or not sheet.is_title_sheet:
                log.info("Skipping non-title sheet: %s", ws.title)
                continue
            log.info("Processing sheet '%s' (header row %d, link col %s)",
                     ws.title, sheet.header_row, sheet.link_col)
            excel_writer.ensure_review_columns(ws, sheet)

            for row in excel_writer.iter_data_rows(ws, sheet):
                if start_row and row < start_row:
                    continue
                if end_row and row > end_row:
                    break
                # Skip totally empty rows.
                if self._row_is_empty(ws, sheet, row):
                    continue
                self.stats["total_rows_seen"] += 1

                link = excel_writer.extract_link(ws, row, sheet.link_col)
                if not link:
                    self.stats["skipped_rows"] += 1
                    self.audit.write_row(
                        timestamp=datetime.now().isoformat(timespec="seconds"),
                        workbook=workbook_name, sheet=ws.title, row=row, link="",
                        status="skipped", confidence="", changed_fields="",
                        review_needed="", error_message="no document link",
                    )
                    continue

                self.stats["linked_rows"] += 1

                if self.audit.already_done(workbook_name, ws.title, row):
                    log.info("Resume: row %s already processed, skipping.", row)
                    continue

                # Mode limits.
                if self.mode == "test" and processed_links >= max_test:
                    log.info("Test mode reached %d linked rows - stopping.", max_test)
                    return False
                if max_rows and processed_links >= int(max_rows):
                    return False

                stop = self._process_row(
                    ws, sheet, row, link, viewer, router, excel_writer,
                    workbook_name, safe_thr,
                )
                processed_links += 1
                if stop:  # login expired
                    return True

                self._wipe_temp()
                time.sleep(delay)
        return False

    def _process_row(self, ws, sheet, row, link, viewer, router, excel_writer,
                     workbook_name, safe_thr) -> bool:
        """Process a single linked row. Returns True if login expired (stop)."""
        retries = int(self.config.get("max_retries_per_row", 3))
        capture = None
        for attempt in range(1, retries + 1):
            try:
                capture = viewer.capture_document(link)
            except Exception as exc:
                log.warning("Row %s capture attempt %d error: %s", row, attempt, exc)
                continue
            if capture.login_expired:
                self._log_failed(ws, sheet, row, link, "login_expired",
                                 "county login expired", excel_writer, workbook_name)
                return True
            if capture.ok:
                break
            log.info("Row %s attempt %d: %s", row, attempt, capture.error or "no image")

        if not capture or not capture.ok:
            err = (capture.error if capture else "capture failed") or "unreadable"
            status = "blocked" if "block" in err.lower() else "failed"
            self._log_failed(ws, sheet, row, link, status, err,
                             excel_writer, workbook_name)
            return False

        # AI extraction (primary, then conditional validators).
        try:
            # First pass: run primary only to detect change, decide validation.
            result = router.run(capture.images, row_changed=False)
            merged = result.merged
            changed = excel_writer.compare_row(sheet, ws, row, merged)
            if changed and not result.validators_used and (
                self.config.get("validate_changed_rows", True)
                or self.config.get("validate_low_confidence_rows", True)
            ):
                # Re-run with validators now that we know the row changed.
                result = router.run(capture.images, row_changed=True)
                merged = result.merged
                changed = excel_writer.compare_row(sheet, ws, row, merged)
        except Exception as exc:
            log.exception("AI extraction failed for row %s", row)
            self._log_failed(ws, sheet, row, link, "error",
                             f"AI error: {exc}", excel_writer, workbook_name)
            return False

        payload = {
            "merged": merged,
            "status": "processed",
            "confidence": result.confidence,
            "changed_fields": changed,
            "consensus_fields": result.consensus_fields,
            "evidence_summary": result.evidence_summary,
            "needs_human_review": result.needs_human_review,
            "error": "",
            "link": link,
            "viewer_method": capture.method,
            "model_used": ", ".join(result.models_used),
            "validators_used": result.validators_used,
        }
        color = excel_writer.write_review(ws, sheet, row, payload, self.config)

        # Stats.
        self.stats["processed_rows"] += 1
        if changed:
            self.stats["changed_rows"] += 1
        if result.confidence >= safe_thr and not changed:
            self.stats["high_confidence_rows"] += 1
        if result.needs_human_review or color == "red":
            self.stats["review_needed_rows"] += 1

        self.audit.write_row(
            timestamp=datetime.now().isoformat(timespec="seconds"),
            workbook=workbook_name, sheet=ws.title, row=row, link=link,
            status=color, confidence=round(result.confidence, 3),
            changed_fields="|".join(changed),
            review_needed="yes" if result.needs_human_review else "no",
            error_message="",
        )
        log.info("Row %s -> %s (conf=%.2f, changed=%s)",
                 row, color, result.confidence, changed)
        return False

    # -- helpers -------------------------------------------------------------
    def _row_is_empty(self, ws, sheet, row) -> bool:
        for field in ("instrument_number", "grantor", "grantee", "book_page", "doc_link"):
            col = sheet.field_to_col.get(field)
            if col and ws.cell(row=row, column=col).value not in (None, ""):
                return False
        return True

    def _log_failed(self, ws, sheet, row, link, status, error,
                    excel_writer, workbook_name) -> None:
        self.stats["failed_rows"] += 1
        self.stats["review_needed_rows"] += 1
        payload = {
            "merged": {}, "status": status, "confidence": 0.0,
            "changed_fields": [], "consensus_fields": [],
            "evidence_summary": "", "needs_human_review": True,
            "error": error, "link": link, "viewer_method": "",
            "model_used": "", "validators_used": [],
        }
        excel_writer.write_review(ws, sheet, row, payload, self.config)
        self.audit.write_row(
            timestamp=datetime.now().isoformat(timespec="seconds"),
            workbook=workbook_name, sheet=ws.title, row=row, link=link,
            status=status, confidence=0, changed_fields="",
            review_needed="yes", error_message=error,
        )
        log.warning("Row %s FAILED (%s): %s", row, status, error)

    def _wipe_temp(self) -> None:
        if not self.config.get("delete_temp_after_each_row", True):
            return
        if self.config.get("debug_save_screenshots", False):
            return
        for name in os.listdir(self.temp_dir):
            p = os.path.join(self.temp_dir, name)
            try:
                if os.path.isfile(p):
                    os.remove(p)
                elif os.path.isdir(p):
                    shutil.rmtree(p)
            except Exception:
                pass

    def _print_summary(self) -> None:
        print("\n================ SUMMARY ================")
        for k, v in self.stats.items():
            print(f"  {k:24s}: {v}")
        print("=========================================\n")

    def _deliver(self, backend) -> None:
        files = [self.output_path,
                 self.audit.run_log_path,
                 self.audit.summary_path]
        if backend.mode == "none":
            print("Google Drive upload is NOT configured.")
            print("To upload manually:")
            print(f"  1. Open the Drive folder: {self.config.get('drive_folder_url')}")
            print(f"  2. Create a folder named like "
                  f"{self.config.get('output_folder_prefix')}_"
                  f"{datetime.now().strftime('%Y-%m-%d_%H%M')}")
            print(f"  3. Upload these files into it:")
            for f in files:
                print(f"       {f}")
            return
        try:
            dest = backend.upload_outputs(files, self.config.get("output_folder_prefix"))
            print(f"\nUploaded output to: {dest}\n")
        except Exception as exc:
            log.error("Upload failed: %s", exc)
            print(f"[WARN] Upload failed ({exc}). Files remain in output/ for manual upload.")


# ---------------------------------------------------------------------------
# Upload-only mode
# ---------------------------------------------------------------------------


def upload_latest(config: dict) -> int:
    import drive_sync

    output_dir = os.path.join(HERE, "output")
    logs_dir = os.path.join(HERE, "logs")
    reviews = [
        os.path.join(output_dir, n)
        for n in os.listdir(output_dir)
        if n.lower().endswith(".xlsx")
    ]
    if not reviews:
        print("No output workbook found in output/. Run a review first.")
        return 1
    latest = max(reviews, key=os.path.getmtime)
    files = [latest,
             os.path.join(logs_dir, "run_log.csv"),
             os.path.join(logs_dir, "summary.csv")]
    backend = drive_sync.build_backend(config)
    if backend.mode == "none":
        print("Google Drive upload is NOT configured. Files to upload manually:")
        for f in files:
            print(f"  {f}")
        return 0
    dest = backend.upload_outputs(files, config.get("output_folder_prefix"))
    print(f"Uploaded latest output to: {dest}")
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="HorizonTitleLinkExtractor")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--login-setup", action="store_true")
    group.add_argument("--test", action="store_true")
    group.add_argument("--full", action="store_true")
    group.add_argument("--upload-only", action="store_true")
    args = parser.parse_args(argv)

    setup_logging()
    load_env()
    config = load_config()

    if args.login_setup:
        from browser_viewer import run_login_setup

        ok = run_login_setup(config)
        return 0 if ok else 1

    if args.upload_only:
        return upload_latest(config)

    mode = "test" if args.test else "full"
    try:
        return Job(config, mode).run()
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        return 130
    except Exception:
        log.exception("Fatal error in job")
        return 1


if __name__ == "__main__":
    sys.exit(main())
