#!/bin/bash

# Скрипт для проверки статуса Telegram бота

BOT_DIR="/Users/sergey/Work/AI PROJECTS/CHATBOT"
BOT_SCRIPT="bot.py"
SUPERVISOR_SCRIPT="$BOT_DIR/supervise_bot.sh"
PID_FILE="$BOT_DIR/.bot_pid"
LOG_FILE="$BOT_DIR/bot.log"

echo "================================================"
echo "Статус Telegram бота"
echo "================================================"

# Проверка супервизора по PID файлу
if [ -f "$PID_FILE" ]; then
    SAVED_PID=$(cat "$PID_FILE")
    if ps -p $SAVED_PID > /dev/null 2>&1; then
        echo "✅ Супервизор работает (PID: $SAVED_PID)"
        
        # Показываем информацию о процессе
        ps -p $SAVED_PID -o pid,etime,rss,command | tail -1 2>/dev/null || true
        
        # Показываем последние строки лога
        if [ -f "$LOG_FILE" ]; then
            echo ""
            echo "📝 Последние 10 строк лога:"
            echo "------------------------------------------------"
            tail -10 "$LOG_FILE"
        fi
    else
        echo "⚠️  Сохраненный PID ($SAVED_PID) не работает"
        rm -f "$PID_FILE"
    fi
else
    echo "⚠️  PID файл не найден"
fi

echo ""
echo "🔍 Процессы супервизора:"
echo "------------------------------------------------"
SUPERVISOR_RUNNING=$(pgrep -fl "$SUPERVISOR_SCRIPT" || true)
if [ -n "$SUPERVISOR_RUNNING" ]; then
    echo "$SUPERVISOR_RUNNING"
else
    echo "❌ Супервизор не запущен"
fi

echo ""
echo "🔍 Все процессы python с bot.py:"
echo "------------------------------------------------"
RUNNING=$(pgrep -fl "$BOT_DIR/$BOT_SCRIPT" || true)

if [ -n "$RUNNING" ]; then
    echo "$RUNNING"
    
    # Подсчет процессов
    COUNT=$(echo "$RUNNING" | wc -l | tr -d ' ')
    echo ""
    if [ $COUNT -gt 1 ]; then
        echo "⚠️  ВНИМАНИЕ: Запущено $COUNT процессов! Должен быть только один."
        echo "   Используйте ./stop_bot.sh для остановки всех процессов"
        echo "   затем ./start_bot.sh для запуска одного экземпляра"
    fi
else
    echo "❌ Бот не запущен"
    echo ""
    echo "Для запуска используйте: ./start_bot.sh"
fi

echo "================================================"
