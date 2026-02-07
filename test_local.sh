#!/bin/bash
# Run bot locally with test token

# Load local environment
export $(grep -v '^#' .env.local | xargs)

echo "🧪 Starting LOCAL test bot..."
echo "📱 Use your TEST bot on Telegram (not the production bot)"
echo ""
python3 bot.py
