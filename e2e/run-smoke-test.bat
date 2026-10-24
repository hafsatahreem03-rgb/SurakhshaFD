@echo off
REM Browser smoke test of the full judge demo in Microsoft Edge. Start the app (start.bat) and reset the demo first.
cd /d "%~dp0"
if not exist .venv (
  py -3 -m venv .venv
  .venv\Scripts\python -m pip install -r requirements.txt -q
)
.venv\Scripts\python demo_smoke.py %*
pause
