#!/bin/bash
PROJECT_DIR="/vol1/1000/Project/trim-music-hub"
LOG_DIR="$PROJECT_DIR/data/logs"
mkdir -p "$LOG_DIR"

echo "=== Starting TRIM Music Hub Frontend Vite Dev Server ==="
# 停止可能存在的旧 Vite 实例 (端口 5175)
pkill -f "vite.*5175" 2>/dev/null
sleep 1

cd "$PROJECT_DIR/frontend"
nohup npx vite --host 0.0.0.0 --port 5175 > "$LOG_DIR/frontend_dev.log" 2>&1 &
PID=$!

echo "✅ Vite dev server started (PID: $PID)"
echo "📡 Frontend Dev URL: http://192.168.0.2:5175"
echo "🌐 Proxy URL: https://music.miong.me:9481"
