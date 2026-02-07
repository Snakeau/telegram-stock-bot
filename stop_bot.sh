#!/bin/bash

# Скрипт для остановки Telegram бота

BOT_DIR="/Users/sergey/Work/AI PROJECTS/CHATBOT"
BOT_SCRIPT="bot.py"
PID_FILE="$BOT_DIR/.bot_pid"

echo "================================================"
echo "Остановка Telegram бота..."
echo "================================================"

# Остановка по PID из файла
if [ -f "$PID_FILE" ]; then
    SAVED_PID=$(cat "$PID_FILE")
    if ps -p $SAVED_PID > /dev/null 2>&1; then
        echo "🛑 Остановка процесса $SAVED_PID..."
        kill -15 $SAVED_PID 2>/dev/null
        sleep 1
        
        # Если процесс все еще работает, убить принудительно
        if ps -p $SAVED_PID > /dev/null 2>&1; then
            kill -9 $SAVED_PID 2>/dev/null
        fi
        
        rm -f "$PID_FILE"
        echo "✓ Процесс $SAVED_PID остановлен"
    else
        echo "⚠️  Процесс $SAVED_PID уже не работает"
        rm -f "$PID_FILE"
    fi
fi

# Поиск и остановка всех оставшихся процессов
RUNNING_PIDS=$(ps aux | grep -E "python.*$BOT_SCRIPT" | grep -v grep | awk '{print $2}')

if [ -n "$RUNNING_PIDS" ]; then
    echo "🔍 Найдены дополнительные процессы: $RUNNING_PIDS"
    for PID in $RUNNING_PIDS; do
        kill -9 $PID 2>/dev/null && echo "   ✓ Процесс $PID остановлен"
    done
else
    echo "✓ Дополнительных процессов не найдено"
fi

# Финальная проверка
sleep 1
STILL_RUNNING=$(ps aux | grep -E "python.*$BOT_SCRIPT" | grep -v grep | wc -l)

if [ $STILL_RUNNING -eq 0 ]; then
    echo "✅ Все процессы бота остановлены"
    echo "================================================"
else
    echo "⚠️  Возможно, некоторые процессы все еще работают"
    ps aux | grep -E "python.*$BOT_SCRIPT" | grep -v grep
    echo "================================================"
fi
