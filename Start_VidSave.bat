@echo off
title VidSave - Video Downloader Server
color 0A

echo ========================================
echo    VidSave - Video Downloader Server
echo ========================================
echo.
echo Starting server...
echo.

cd /d "%~dp0"

REM Check if Python is installed
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from https://python.org
    pause
    exit /b 1
)

REM Check if virtual environment exists
if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    python -m venv .venv
    
    echo Installing dependencies...
    call .venv\Scripts\activate.bat
    pip install flask flask-cors yt-dlp
)

echo.
echo ========================================
echo Server is running!
echo ========================================
echo.
echo Open your browser and go to:
echo http://localhost:5000
echo.
echo Press Ctrl+C to stop the server
echo ========================================
echo.

.venv\Scripts\python.exe server.py

pause
