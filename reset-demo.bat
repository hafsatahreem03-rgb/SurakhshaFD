@echo off
REM Backs up the database (backend\data\backups), wipes it, and reloads the fictional demo data.
REM It asks you to type YES first. Run it before every judge demo.
cd /d "%~dp0backend"
.venv\Scripts\python -m app.cli reset-demo
echo.
echo If the backend is running, just refresh the browser and sign in again.
pause
