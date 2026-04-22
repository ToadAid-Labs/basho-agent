#!/bin/bash

# AI Crypto Trading Bot - Universal Launcher
# This script starts both the Backend API and the Telegram Bot.

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${CYAN}🚀 Starting AI Crypto Trading Bot System...${NC}"

if [ -d ".venv" ]; then
    source .venv/bin/activate
    PYTHON="$(pwd)/.venv/bin/python"
elif [ -d "venv" ]; then
    source venv/bin/activate
    PYTHON="$(pwd)/venv/bin/python"
else
    echo -e "${YELLOW}⚠️  Warning: Virtual environment not found. Running with system python...${NC}"
    PYTHON=python3
fi

echo -e "${GREEN}📡 Starting Backend API (background)...${NC}"
"$PYTHON" backend/app.py > server.log 2>&1 &
BACKEND_PID=$!

sleep 2

echo -e "${GREEN}🤖 Starting Telegram Bot interface...${NC}"
echo -e "${YELLOW}💡 Note: Press Ctrl+C to stop both the bot and the backend.${NC}"

"$PYTHON" agent.py bot

echo -e "${CYAN}🛑 Shutting down system...${NC}"
kill $BACKEND_PID
echo -e "${GREEN}✅ Done.${NC}"