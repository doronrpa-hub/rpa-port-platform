@echo off
cd /d C:\Users\doron\rpa-port-platform\functions
echo ============================================================
echo   OVERNIGHT LEARN — Started %date% %time%
echo   Step 0: Clean old dry-run results from Firestore
echo   Step 1: Dry-run all Graph emails (FREE, no AI)
echo   Step 2: Rebuild indexes from everything learned
echo ============================================================
echo.

echo [%time%] Cleaning old dry-run results...
.\venv\Scripts\python.exe -u cleanup_old_results.py
echo.

echo [%time%] Starting dry-run on all Graph emails...
.\venv\Scripts\python.exe -u batch_reprocess.py --dry-run --source graph
echo.
echo [%time%] Dry-run complete.
echo.

echo [%time%] Starting deep learning (rebuild indexes)...
.\venv\Scripts\python.exe -u deep_learn.py
echo.
echo [%time%] Deep learning complete.
echo.

echo ============================================================
echo   ALL DONE — %date% %time%
echo ============================================================
pause
