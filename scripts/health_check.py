import os, sys
from pathlib import Path

def check():
    print("=== DATABOSSX HEALTH CHECK ===")
    v = sys.version_info
    print(f"Python Version: {v.major}.{v.minor}.{v.micro}")
    if v.major < 3 or (v.major == 3 and v.minor < 11):
        print("[FAIL] Python 3.11+ required.")
        sys.exit(1)
    else: print("[PASS] Python version meets requirements.")

    root = Path(__file__).resolve().parent.parent
    req_dirs = ["app", "agents", "tools", "workflows", "scripts", "tests", "docs", "data", "outputs", "logs", "backups", "quarantine", "config", "reports", "agent_outputs", "prompts", ".auth", "temp"]
    missing = [d for d in req_dirs if not (root / d).exists()]
    if missing: print(f"[WARN] Missing dirs: {', '.join(missing)}")
    else: print("[PASS] All required directories exist.")

    for f in [".env.example", ".gitignore", "DATABOSSX_SECURITY_POLICY.md", "DATABOSSX_PROJECT_MAP.md"]:
        if (root / f).exists(): print(f"[PASS] {f} exists.")
        else: print(f"[FAIL] Missing {f}")

    print("=== HEALTH CHECK COMPLETE ===")

if __name__ == "__main__":
    check()
