@echo off
REM Records the SurakshaFD walkthrough video: male AI narration, caption band, subtle sounds (4-5 min video).
REM Output: video\SurakshaFD_Walkthrough.mp4 and .srt. Resets the demo data first.
cd /d "%~dp0e2e"
if not exist .venv (
  py -3 -m venv .venv
  .venv\Scripts\python -m pip install -r requirements.txt -q
)
.venv\Scripts\python -m pip install -r requirements.txt -q
set PLAYWRIGHT_BROWSERS_PATH=%~dp0e2e\.pw-browsers
.venv\Scripts\python -m playwright install ffmpeg
REM Narration voice: Piper "en_US-john-medium" (male, public-domain LibriVox recordings), offline after this download.
if not exist .voices\en_US-john-medium.onnx .venv\Scripts\python -m piper.download_voices en_US-john-medium --download-dir .voices
.venv\Scripts\python make_video.py
echo.
echo Open the "video" folder to find SurakshaFD_Walkthrough.mp4
pause
