#!/bin/bash
# ============================================================================
# SHEEPCARE — OpenAgri Farm Calendar setup script
# Clones and configures the Farm Calendar service from GitHub.
# Run: chmod +x setup_farmcalendar.sh && ./setup_farmcalendar.sh
# ============================================================================

REPO_URL="https://github.com/agstack/OpenAgri-FarmCalendar.git"
TARGET_DIR="farmcalendar"

if [ -d "$TARGET_DIR" ]; then
    echo "✅ Directory '$TARGET_DIR' already exists."
    exit 0
fi

echo "📥 Cloning OpenAgri Farm Calendar..."
git clone "$REPO_URL" "$TARGET_DIR"

if [ $? -ne 0 ]; then
    echo "❌ Failed to clone repository."
    exit 1
fi

# Copy default .env
cp "$TARGET_DIR/.env.sample" "$TARGET_DIR/.env" 2>/dev/null

echo "✅ Farm Calendar ready! Configure $TARGET_DIR/.env if needed."
