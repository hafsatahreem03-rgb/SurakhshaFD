@echo off
REM Runs both Judge Demonstration Mode demos end to end in Microsoft Edge and verifies the database.
REM Resets the demo data first. Starts the servers if they are not running.
cd /d "%~dp0"
if not exist .venv (
  py -3 -m venv .venv
  .venv\Scripts\python -m pip install -r requirements.txt -q
)
set PLAYWRIGHT_BROWSERS_PATH=%~dp0.pw-browsers
.venv\Scripts\python judge_demo_test.py %*
pause
