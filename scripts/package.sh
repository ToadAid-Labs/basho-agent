#!/bin/bash

# Packaging script for Telegram Trading Bot
# Creates a clean distribution archive for installation on other systems

PACKAGE_NAME="trading-bot"
VERSION="1.6.0"
DIST_DIR="dist"
RELEASE_DIR="releases"
TARBALL="${PACKAGE_NAME}-v${VERSION}.tar.gz"
ZIPFILE="${PACKAGE_NAME}-v${VERSION}.zip"

echo "📦 Packaging Telegram Trading Bot v${VERSION}..."

# Create directories
rm -rf $DIST_DIR
mkdir -p $DIST_DIR
mkdir -p $RELEASE_DIR

# List of essential directories to include
DIRS=(
    "backend"
    "core"
    "market_data"
    "memory"
    "monitoring"
    "tools"
    "systemd"
    "docs"
    "scripts"
    "workspace"
)

# List of essential files to include
FILES=(
    "agent.py"
    "execution_layer.py"
    "risk_management.py"
    "trading_strategies.py"
    "requirements.txt"
    "setup.sh"
    "setup.bat"
    "run_bot.sh"
    "run_bot.bat"
    "OPERATION.md"
    "README.md"
    "FEATURES.md"
    "ROADMAP.md"
    ".env.example"
)

# Copy directories
echo "📁 Copying directories..."
for dir in "${DIRS[@]}"; do
    if [ -d "$dir" ]; then
        cp -r "$dir" "$DIST_DIR/"
        # Clean up pycache and local DBs in copied directories
        find "$DIST_DIR/$dir" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
        find "$DIST_DIR/$dir" -name "*.db" -delete 2>/dev/null
        if [ "$dir" = "workspace" ]; then
            find "$DIST_DIR/workspace/agent_memory" -type f ! -name "README.md" -delete 2>/dev/null
            find "$DIST_DIR/workspace/scratch" -type f ! -name "README.md" -delete 2>/dev/null
        fi
    else
        echo "⚠️  Warning: Directory $dir not found, skipping."
    fi
done

# Copy files
echo "📄 Copying files..."
for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        cp "$file" "$DIST_DIR/"
    else
        echo "⚠️  Warning: File $file not found, skipping."
    fi
done

# Create the Linux/macOS tarball
echo "🗜️  Creating archive $TARBALL..."
tar -czf "$RELEASE_DIR/$TARBALL" -C $DIST_DIR .

# Create the Windows zip archive
echo "🗜️  Creating archive $ZIPFILE..."
if command -v zip >/dev/null 2>&1; then
    (cd "$DIST_DIR" && zip -qr "../$RELEASE_DIR/$ZIPFILE" .)
else
    echo "⚠️  Warning: zip command not found; skipping Windows zip archive."
fi

# Clean up staging area
rm -rf $DIST_DIR

echo ""
echo "✅ Packaging complete!"
echo "📍 Linux/macOS archive: $RELEASE_DIR/$TARBALL"
if [ -f "$RELEASE_DIR/$ZIPFILE" ]; then
    echo "📍 Windows archive: $RELEASE_DIR/$ZIPFILE"
fi
echo ""
echo "To distribute:"
echo "Share the .tar.gz for Linux/macOS and the .zip for Windows."
