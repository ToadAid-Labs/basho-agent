#!/bin/bash
set -euo pipefail

# Telegram Trading Bot Setup Script
# This script sets up the environment and dependencies

echo "🚀 Setting up Telegram Trading Bot & Web UI..."
echo ""

# Check Python version
echo "📋 Checking Python version..."
if command -v python3 &>/dev/null; then
    python_version=$(python3 --version 2>&1 | awk '{print $2}')
    echo "✅ Found Python $python_version"
else
    echo "❌ Python 3 not found! Please install Python 3.8 or higher."
    exit 1
fi

# Create virtual environment
if [ ! -d "venv" ]; then
    echo ""
    echo "🐍 Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo ""
echo "🔴 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo ""
echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Check for .env file
echo ""
echo "🔐 Setting up environment variables..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "Creating .env from .env.example..."
        cp .env.example .env
        echo "⚠️  Please edit .env and add your credentials!"
    else
        echo "❌ .env.example not found! Please create a .env file manually."
    fi
else
    echo "✅ .env file already exists"
fi

# Initialize Database
echo ""
echo "🗄️ Initializing database..."
python scripts/init_db.py

# Make scripts executable
chmod +x setup.sh scripts/*.sh

echo ""
echo "🎉 Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env and add your credentials:"
echo "   - TWAK_ACCESS_ID (from Trust Wallet)"
echo "   - TWAK_HMAC_SECRET (from Trust Wallet)"
echo "   - TELEGRAM_BOT_TOKEN (from @BotFather)"
echo "   - DASHBOARD_PASSWORD (for Web UI)"
echo ""
echo "2. Start the AI system (Bot + Backend):"
echo "   - Run: ./run_bot.sh"
echo ""
echo "3. (Optional) Start components separately:"
echo "   - Telegram Bot: python3 agent.py bot"
echo "   - Web Dashboard: python3 backend/app.py"
echo ""
echo "4. (Optional) Run background services (Linux):"
echo "   - Run: ./scripts/install_service.sh"
echo "   - Follow the instructions to install systemd services."
echo ""
echo "5. (Optional) Run setup verification after configuring credentials:"
echo "   - Run: python tests/test_setup.py"
echo ""
echo "6. Access the dashboard at http://localhost:5000 📱"
