@echo off
REM Starts the backend (port 8000) and frontend (port 5173) in two windows and opens the browser.
cd /d "%~dp0"
if not exist backend\.venv (echo Run setup.bat first. & pause & exit /b 1)
start "SurakshaFD backend (port 8000)" cmd /k "cd /d %~dp0backend && .venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
REM Frontend: production build + preview server (no live-reload, so nothing reloads mid-demo).
REM For development with hot reload, run "npm run dev" in the frontend folder instead.
start "SurakshaFD frontend (port 5173)" cmd /k "cd /d %~dp0frontend && npm run demo"
echo Waiting for the servers to start...
timeout /t 20 /nobreak >nul
start "" http://localhost:5173
echo SurakshaFD is starting. Close the two server windows to stop it.
