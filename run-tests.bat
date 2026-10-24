@echo off
REM Runs the backend automated tests (uses a temporary database; your demo data is untouched).
cd /d "%~dp0backend"
.venv\Scripts\python -m pytest -v
pause
