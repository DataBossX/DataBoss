"""Organize a messy source folder (e.g. D:/Desktop/Horizon).

Safely:
    * extracts every .zip (recursively, including zips inside zips) with
      zip-slip protection,
    * inventories every file with a SHA-256 hash, size, and category,
    * de-duplicates by content -- identical files are MOVED (never deleted) to
      ``_quarantine/duplicates`` so the action is reversible,
    * quarantines obvious junk (zero-byte files, Thumbs.db, .DS_Store, Office
      ``~$`` lock files) to ``_quarantine/trash``,
    * writes an inventory report (Markdown + JSON) and returns the list of
      workbooks found so the validation agent can process them.

Nothing is destroyed. The operator can inspect ``_quarantine`` and delete it
themselves once satisfied.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_JUNK_NAMES = {"thumbs.db", ".ds_store", "desktop.ini"}
_CATEGORIES = {
    "workbook": {".xlsx", ".xlsm", ".xls"},
    "pdf": {".pdf"},
    "image": {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".gif", ".bmp"},
    "document": {".doc", ".docx", ".txt", ".rtf", ".csv"},
    "archive": {".zip", ".7z", ".rar"},
}
_QUARANTINE = "_quarantine"


def _category(path: Path) -> str:
    ext = path.suffix.lower()
    for cat, exts in _CATEGORIES.items():
        if ext in exts:
            return cat
    return "other"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_junk(path: Path) -> bool:
    name = path.name.lower()
    if name in _JUNK_NAMES:
        return True
    if name.startswith("~$"):  # Office lock/temp files
        return True
    return False


@dataclass
class FileRecord:
    path: str
    rel: str
    size: int
    sha256: str
    category: str


@dataclass
class OrganizeResult:
    root: str
    extracted_zips: list[str] = field(default_factory=list)
    files: list[FileRecord] = field(default_factory=list)
    duplicates: list[dict] = field(default_factory=list)
    trash: list[str] = field(default_factory=list)
    workbooks: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def summary(self) -> dict:
        return {
            "root": self.root,
            "extracted_zips": len(self.extracted_zips),
            "files": len(self.files),
            "duplicates_quarantined": len(self.duplicates),
            "trash_quarantined": len(self.trash),
            "workbooks": len(self.workbooks),
            "errors": len(self.errors),
        }


class WorkspaceOrganizer:
    def __init__(self, *, quarantine: bool = True) -> None:
        #: When False, duplicates/junk are only reported, never moved.
        self.quarantine = quarantine

    def run(self, root: str | Path) -> OrganizeResult:
        root = Path(root).resolve()
        result = OrganizeResult(root=str(root))
        if not root.is_dir():
            result.errors.append(f"Not a directory: {root}")
            return result

        quarantine_dir = root / _QUARANTINE
        self._extract_all_zips(root, quarantine_dir, result)
        self._inventory(root, quarantine_dir, result)
        self._dedupe(root, quarantine_dir, result)
        self._write_report(root, result)
        return result

    # -- zip extraction -----------------------------------------------------
    def _extract_all_zips(self, root: Path, quarantine_dir: Path,
                          result: OrganizeResult) -> None:
        processed: set[str] = set()
        # Loop so zips nested inside freshly-extracted zips are also handled.
        while True:
            pending = [p for p in root.rglob("*.zip")
                       if str(p) not in processed and _QUARANTINE not in p.parts]
            if not pending:
                break
            for zip_path in pending:
                processed.add(str(zip_path))
                dest = zip_path.with_suffix("")  # extract beside the archive
                if dest.exists() and any(dest.iterdir()):
                    continue  # already extracted
                try:
                    self._safe_extract(zip_path, dest)
                    result.extracted_zips.append(str(zip_path))
                except Exception as exc:  # noqa: BLE001
                    result.errors.append(f"extract {zip_path}: {exc}")

    @staticmethod
    def _safe_extract(zip_path: Path, dest: Path) -> None:
        dest.mkdir(parents=True, exist_ok=True)
        dest_res = dest.resolve()
        with zipfile.ZipFile(zip_path) as zf:
            for member in zf.namelist():
                target = (dest / member).resolve()
                # zip-slip guard: refuse any member that escapes dest.
                if not str(target).startswith(str(dest_res)):
                    raise RuntimeError(f"unsafe path in archive: {member}")
            zf.extractall(dest)

    # -- inventory ----------------------------------------------------------
    def _inventory(self, root: Path, quarantine_dir: Path,
                   result: OrganizeResult) -> None:
        trash_dir = quarantine_dir / "trash"
        for path in sorted(root.rglob("*")):
            if _QUARANTINE in path.parts or not path.is_file() or path.is_symlink():
                continue
            try:
                if _is_junk(path) or path.stat().st_size == 0:
                    result.trash.append(str(path))
                    self._move(path, trash_dir, root)
                    continue
                rec = FileRecord(path=str(path),
                                 rel=str(path.relative_to(root)),
                                 size=path.stat().st_size,
                                 sha256=_sha256(path),
                                 category=_category(path))
                result.files.append(rec)
                if rec.category == "workbook" and not path.name.startswith("~$"):
                    result.workbooks.append(str(path))
            except OSError as exc:
                result.errors.append(f"inventory {path}: {exc}")

    # -- dedupe -------------------------------------------------------------
    def _dedupe(self, root: Path, quarantine_dir: Path,
                result: OrganizeResult) -> None:
        dup_dir = quarantine_dir / "duplicates"
        by_hash: dict[str, list[FileRecord]] = {}
        for rec in result.files:
            by_hash.setdefault(rec.sha256, []).append(rec)
        kept_files: list[FileRecord] = []
        for digest, recs in by_hash.items():
            if len(recs) == 1:
                kept_files.append(recs[0])
                continue
            recs_sorted = sorted(recs, key=lambda r: (len(r.rel), r.rel))
            keeper = recs_sorted[0]
            kept_files.append(keeper)
            for dup in recs_sorted[1:]:
                result.duplicates.append({"kept": keeper.rel, "duplicate": dup.rel,
                                          "sha256": digest})
                self._move(Path(dup.path), dup_dir, root)
                if dup.path in result.workbooks:
                    result.workbooks.remove(dup.path)
        result.files = kept_files

    # -- helpers ------------------------------------------------------------
    def _move(self, path: Path, dest_root: Path, root: Path) -> None:
        if not self.quarantine:
            return
        try:
            rel = path.relative_to(root)
        except ValueError:
            rel = Path(path.name)
        target = dest_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target = target.with_name(f"{target.stem}_{_sha256(path)[:8]}{target.suffix}")
        shutil.move(str(path), str(target))

    def _write_report(self, root: Path, result: OrganizeResult) -> None:
        report_dir = root / _QUARANTINE
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "inventory.json").write_text(
            json.dumps({"summary": result.summary(),
                        "files": [f.__dict__ for f in result.files],
                        "duplicates": result.duplicates,
                        "trash": result.trash,
                        "workbooks": result.workbooks,
                        "errors": result.errors}, indent=2), encoding="utf-8")
        lines = [f"# Workspace Inventory -- {root.name}", "",
                 f"- Files kept: {len(result.files)}",
                 f"- Zips extracted: {len(result.extracted_zips)}",
                 f"- Duplicates quarantined: {len(result.duplicates)}",
                 f"- Trash quarantined: {len(result.trash)}",
                 f"- Workbooks found: {len(result.workbooks)}", ""]
        by_cat: dict[str, int] = {}
        for f in result.files:
            by_cat[f.category] = by_cat.get(f.category, 0) + 1
        lines.append("## By category")
        for cat, n in sorted(by_cat.items()):
            lines.append(f"- {cat}: {n}")
        lines.append("")
        lines.append("## Workbooks")
        for wb in result.workbooks:
            lines.append(f"- `{wb}`")
        if result.duplicates:
            lines.append("")
            lines.append("## Duplicates quarantined (reversible)")
            for d in result.duplicates:
                lines.append(f"- `{d['duplicate']}` == `{d['kept']}`")
        (report_dir / "inventory.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv: Optional[list[str]] = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Organize a source workspace.")
    parser.add_argument("root", help="Folder to organize (e.g. D:/Desktop/Horizon)")
    parser.add_argument("--report-only", action="store_true",
                        help="Report duplicates/trash without moving anything.")
    args = parser.parse_args(argv)
    result = WorkspaceOrganizer(quarantine=not args.report_only).run(args.root)
    print(json.dumps(result.summary(), indent=2))
    for wb in result.workbooks:
        print("workbook:", wb)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
