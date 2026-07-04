"""Root entrypoint for the Grocery Report pipeline.

Usage:
    python run_report_pipeline.py --root "D:\\DataBoss\\DataBossX_Final_Modular"
    python run_report_pipeline.py                # uses current dir / env var

Outputs land in <root>/output/. Rerunnable and non-destructive.
"""
from report_pipeline.pipeline import main

if __name__ == "__main__":
    raise SystemExit(main())
