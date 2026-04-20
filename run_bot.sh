#!/bin/bash

# AI Crypto Trading Bot - Universal Launcher
# This script starts both the Backend API and the Telegram Bot.

# Colors for output
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${CYAN}🚀 Starting AI Crypto Trading Bot System...${NC}"

# Check for virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo -e "${YELLOW}⚠️  Warning: Virtual environment not found. Running with system python...${NC}"
fi

# 1. Start the Backend API in the background
echo -e "${GREEN}📡 Starting Backend API (background)...${NC}"
python3 backend/app.py > server.log 2>&1 &
BACKEND_PID=$!

# 2. Wait a moment for backend to initialize
sleep 2

# 3. Start the Telegram Bot in the foreground
echo -e "${GREEN}🤖 Starting Telegram Bot interface...${NC}"
echo -e "${YELLOW}💡 Note: Press Ctrl+C to stop both the bot and the backend.${NC}"

# Run the bot
python3 agent.py bot

# Cleanup on exit
echo -e "${CYAN}🛑 Shutting down system...${NC}"
kill $BACKEND_PID
echo -e "${GREEN}✅ Done.${NC}"
