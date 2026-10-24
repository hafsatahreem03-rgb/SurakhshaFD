@echo off
REM SurakshaFD one-time setup for Windows. Double-click or run from Command Prompt.
setlocal
cd /d "%~dp0"
echo ============================================
echo   SurakshaFD setup (SIH 2026 - Team Lynxcode)
echo ============================================

where py >nul 2>nul || (echo [ERROR] Python not found. Install Python 3.11+ from python.org and tick "Add to PATH". & pause & exit /b 1)
where npm >nul 2>nul || (echo [ERROR] Node.js not found. Install Node.js 18+ from nodejs.org. & pause & exit /b 1)
if not exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
  echo [WARNING] Tesseract OCR not found. Install it with:
  echo     winget install UB-Mannheim.TesseractOCR
  echo The app still runs without it, but documents will need manual entry.
)

echo.
echo [1/4] Creating Python environment...
if not exist backend\.venv (
  py -3 -m venv backend\.venv || (echo [ERROR] Could not create the virtual environment. & pause & exit /b 1)
)
backend\.venv\Scripts\python -m pip install --upgrade pip -q
backend\.venv\Scripts\python -m pip install -r backend\requirements.txt -q || (echo [ERROR] pip install failed. See README "Troubleshooting". & pause & exit /b 1)

echo [2/4] Creating backend\.env with a random secret key...
if exist backend\.env goto envdone
for /f "delims=" %%s in ('backend\.venv\Scripts\python -c "import secrets; print(secrets.token_urlsafe(48))"') do set SECRET=%%s
powershell -NoProfile -Command "(Get-Content backend\.env.example) -replace '^SECRET_KEY=.*', 'SECRET_KEY=%SECRET%' | Set-Content backend\.env"
:envdone

echo [3/4] Loading fictional demo data and sample documents...
pushd backend
.venv\Scripts\python -m app.cli reset-demo --yes
.venv\Scripts\python -m app.cli check-ocr
popd

echo [4/4] Installing frontend packages...
pushd frontend
call npm install --no-audit --no-fund || (echo [ERROR] npm install failed. & popd & pause & exit /b 1)
popd

echo.
echo Setup complete. Now run start.bat
pause
