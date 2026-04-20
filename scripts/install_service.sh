#!/bin/bash

# Script to install systemd services for the AI Crypto Trading Bot
# This script substitutes placeholders in the template files with actual paths.

set -e

WORKING_DIRECTORY=$(pwd)
CURRENT_USER=$(whoami)

echo "🛠️ Preparing systemd service files..."
echo "📍 Working Directory: $WORKING_DIRECTORY"
echo "👤 User: $CURRENT_USER"

# Check if templates exist
if [ ! -f "systemd/crypto-bot.service.template" ] || [ ! -f "systemd/crypto-dashboard.service.template" ]; then
    echo "❌ Error: Service templates not found in systemd/ directory."
    exit 1
fi

# Create final service files
sed "s|{{WORKING_DIRECTORY}}|$WORKING_DIRECTORY|g; s|{{USER}}|$CURRENT_USER|g" systemd/crypto-bot.service.template > systemd/crypto-bot.service
sed "s|{{WORKING_DIRECTORY}}|$WORKING_DIRECTORY|g; s|{{USER}}|$CURRENT_USER|g" systemd/crypto-dashboard.service.template > systemd/crypto-dashboard.service

echo "✅ Service files generated in systemd/ directory."
echo ""
echo "📋 To install these services system-wide, run the following commands:"
echo ""
echo "   sudo cp systemd/*.service /etc/systemd/system/"
echo "   sudo systemctl daemon-reload"
echo "   sudo systemctl enable crypto-bot.service"
echo "   sudo systemctl enable crypto-dashboard.service"
echo "   sudo systemctl start crypto-bot.service"
echo "   sudo systemctl start crypto-dashboard.service"
echo ""
echo "📋 Or to install as user-specific services (no sudo required):"
echo ""
echo "   mkdir -p ~/.config/systemd/user/"
echo "   cp systemd/*.service ~/.config/systemd/user/"
echo "   systemctl --user daemon-reload"
echo "   systemctl --user enable crypto-bot.service"
echo "   systemctl --user enable crypto-dashboard.service"
echo "   systemctl --user start crypto-bot.service"
echo "   systemctl --user start crypto-dashboard.service"
echo ""
echo "💡 Tip: User services are great for desktop users and don't require root access."
