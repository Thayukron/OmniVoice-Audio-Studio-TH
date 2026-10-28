@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PATH=D:\ffmpeg\ffmpeg-9.0.2-full_build\bin;%PATH%"
set PYTHONIOENCODING=utf-8
set HF_HUB_DISABLE_SYMLINKS_WARNING=1
start "" cmd /c "timeout /t 15 >nul && start http://localhost:5000"
"venv\Scripts\python.exe" omnivoice_tts_app.py %*
pause
