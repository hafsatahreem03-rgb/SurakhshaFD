@echo off
REM Shows live database contents (row counts, latest FDRs, latest audit entries) - technical proof for judges.
cd /d "%~dp0backend"
.venv\Scripts\python -m app.cli inspect
pause
