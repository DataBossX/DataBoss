@echo off
REM ==== Grocery Report pipeline (Windows) ====
REM Edit PROJECT_ROOT to your real project folder if different.
set PROJECT_ROOT=D:\DataBoss\DataBossX_Final_Modular

echo Running Grocery Report pipeline against %PROJECT_ROOT% ...
python run_report_pipeline.py --root "%PROJECT_ROOT%"

echo.
echo Done. Open the outputs:
echo   %PROJECT_ROOT%\output\status_dashboard.html
echo   %PROJECT_ROOT%\output\Grocery_Report_DRAFT.md
echo   %PROJECT_ROOT%\output\review_required.csv
pause
