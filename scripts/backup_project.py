import os, shutil, datetime
from pathlib import Path

def backup():
    root = Path(__file__).resolve().parent.parent
    b_dir = root / "backups"
    b_dir.mkdir(exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    b_path = b_dir / f"DataBossX_Backup_{ts}"
    ig = shutil.ignore_patterns('backups', 'temp', 'logs', '.env', '.auth', '__pycache__', '.venv', 'data', 'outputs')

    try:
        shutil.copytree(root, b_path, ignore=ig)
        print(f"[SUCCESS] Backup created at {b_path}")
    except Exception as e:
        print(f"[FAIL] Backup failed: {e}")

if __name__ == "__main__":
    backup()
