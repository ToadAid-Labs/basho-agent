@echo off
setlocal enabledelayedexpansion

echo 🚀 Setting up Telegram Trading Bot & Web UI for Windows...
echo.

:: Check for Python
echo 📋 Checking Python version...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python not found! Please install Python 3.8 or higher from python.org.
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

:: Create virtual environment
if not exist "venv" (
    echo.
    echo 🐍 Creating virtual environment...
    python -m venv venv
    echo ✅ Virtual environment created
) else (
    echo ✅ Virtual environment already exists
)

:: Activate virtual environment and install dependencies
echo.
echo 📦 Installing Python dependencies...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

:: Check for .env file
echo.
echo 🔐 Setting up environment variables...
if not exist ".env" (
    if exist ".env.example" (
        echo Creating .env from .env.example...
        copy .env.example .env
        echo ⚠️  Please edit .env and add your credentials!
    ) else (
        echo ❌ .env.example not found! Please create a .env file manually.
    )
) else (
    echo ✅ .env file already exists
)

:: Initialize Database
echo.
echo 🗄️ Initializing database...
python scripts\init_db.py

echo.
echo 🎉 Setup complete!
echo.
echo Next steps:
echo 1. Edit .env and add your credentials:
echo    - TWAK_ACCESS_ID (from Trust Wallet)
echo    - TWAK_HMAC_SECRET (from Trust Wallet)
echo    - TELEGRAM_BOT_TOKEN (from @BotFather)
echo    - DASHBOARD_PASSWORD (for Web UI)
echo.
echo 2. Start the AI system (Bot + Backend):
echo    - Run: run_bot.bat
echo.
echo 3. Start components separately:
echo    - Telegram Bot: python agent.py bot
echo    - Web Dashboard: python backend/app.py
echo.
echo 4. Optional setup verification after configuring credentials:
echo    - Run: python tests\test_setup.py
echo.
echo 5. Access the dashboard at http://localhost:5000 📱
echo.
pause
