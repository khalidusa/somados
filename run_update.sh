#!/bin/bash
# Somados - Daily Flight Updater
# يشتغل تلقائياً كل يوم عبر cron

WORK_DIR="/Users/khaledsameer/Documents/somados"
LOG_FILE="$WORK_DIR/logs/update.log"
MAX_LOGS=30  # احتفظ بآخر 30 يوم فقط

# تدوير اللوق تلقائياً
if [ -f "$LOG_FILE" ]; then
    LINES=$(wc -l < "$LOG_FILE")
    if [ "$LINES" -gt 5000 ]; then
        tail -2000 "$LOG_FILE" > "$LOG_FILE.tmp" && mv "$LOG_FILE.tmp" "$LOG_FILE"
    fi
fi

echo "========================================" >> "$LOG_FILE"
echo "  بدء التحديث: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

/usr/bin/python3 "$WORK_DIR/update_flights.py" >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

echo "  انتهى: $(date '+%Y-%m-%d %H:%M:%S') | Exit: $EXIT_CODE" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
