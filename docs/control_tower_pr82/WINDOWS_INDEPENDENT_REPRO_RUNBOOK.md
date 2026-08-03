# Windows Independent Reproduction

FOR REVIEW - HOLD NO EXTERNAL RELEASE

Run from the exact frozen code commit in a clean worktree:

```powershell
python -m pytest tests\test_control_tower_b1_b7.py -q
python -m pytest tests\test_control_tower_windows_multiprocess.py -q
python -m pytest tests -q
ruff check --select F,I control_tower tests\test_control_tower_b1_b7.py tests\test_control_tower_windows_multiprocess.py
```

Expected: focused B1-B7 PASS, Windows msvcrt/process PASS, full Python suite PASS, and targeted fatal/import lint PASS. A live Drive test requires a separately activated envelope and must not be inferred from these offline tests.
