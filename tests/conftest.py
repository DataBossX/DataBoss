"""Shared pytest configuration: importability + hermetic test artifacts."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
DOTO = ROOT / "doto_image_commander"

# Backend/root first so a bare ``import config`` resolves to backend/config.py.
for _p in (ROOT, BACKEND):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
# DOTO appended (its modules use namespaced ``core.*`` / ``processors.*``).
if str(DOTO) not in sys.path:
    sys.path.append(str(DOTO))

# Redirect DOTO's import-time file side effects (audit log, db, dirs, key file)
# into a throwaway temp directory so tests never touch the repo or a real home.
_DOTO_TMP = Path(tempfile.gettempdir()) / "databossx_doto_test_artifacts"
_DOTO_TMP.mkdir(parents=True, exist_ok=True)
for _var, _val in {
    "DB_PATH": _DOTO_TMP / "test.db",
    "AUDIT_LOG_PATH": _DOTO_TMP / "audit.log",
    "DOWNLOADS_DIR": _DOTO_TMP / "downloads",
    "IMAGES_DIR": _DOTO_TMP / "images",
    "REPORTS_DIR": _DOTO_TMP / "reports",
    "DOTO_KEY_FILE": _DOTO_TMP / "master.key",
}.items():
    os.environ.setdefault(_var, str(_val))
