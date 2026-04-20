@echo off
title AI Crypto Trading Bot - Universal Launcher

echo 🚀 Starting AI Crypto Trading Bot System for Windows...
echo.

:: Check for virtual environment
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo ⚠️  Warning: Virtual environment not found.
)

:: 1. Start the Backend API in a separate minimized window
echo 📡 Starting Backend API...
start /min "Trading Bot Backend" python backend/app.py

:: 2. Wait a moment
timeout /t 3 /nobreak > nul

:: 3. Start the Telegram Bot in this window
echo 🤖 Starting Telegram Bot interface...
echo.
echo 💡 Note: Close this window to stop the bot. 
echo 💡 You may need to manually close the minimized "Trading Bot Backend" window.
echo.

python agent.py bot

pause
