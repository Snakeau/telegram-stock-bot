#!/bin/bash

BOT_DIR="/Users/sergey/Work/AI PROJECTS/CHATBOT"
BOT_SCRIPT="$BOT_DIR/bot.py"
LOG_FILE="$BOT_DIR/bot.log"
LOCK_FILE="/tmp/telegram_bot.lock"

while true; do
    rm -f "$LOCK_FILE"
    env MPLCONFIGDIR="$BOT_DIR/.mplconfig" PYTHONUNBUFFERED=1 "$BOT_DIR/.venv/bin/python" "$BOT_SCRIPT" >> "$LOG_FILE" 2>&1
    EXIT_CODE=$?
    echo "$(date '+%Y-%m-%d %H:%M:%S') | supervisor | bot.py exited with code $EXIT_CODE, restarting in 5s" >> "$LOG_FILE"
    sleep 5
done

