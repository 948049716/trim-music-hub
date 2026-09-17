#!/bin/bash
PROJECT_DIR="/vol1/1000/Project/trim-music-hub"
LOG_DIR="$PROJECT_DIR/data/logs"
BACKEND_PID_FILE="$LOG_DIR/backend_dev.pid"
mkdir -p "$LOG_DIR"

echo "=== Starting TRIM Music Hub Development Servers ==="

# 独立开发后端，避免影响 4175 上运行中的正式容器
if [ -f "$BACKEND_PID_FILE" ]; then
  OLD_BACKEND_PID=$(cat "$BACKEND_PID_FILE" 2>/dev/null)
  if [ -n "$OLD_BACKEND_PID" ] && kill -0 "$OLD_BACKEND_PID" 2>/dev/null; then
    kill "$OLD_BACKEND_PID" 2>/dev/null
    sleep 1
  fi
fi
cd "$PROJECT_DIR"
nohup env PORT=4275 HOST=127.0.0.1 node server.mjs > "$LOG_DIR/backend_dev.log" 2>&1 &
BACKEND_PID=$!
echo "$BACKEND_PID" > "$BACKEND_PID_FILE"

# 停止可能存在的旧 Vite 实例 (端口 5175)
pkill -f "vite.*5175" 2>/dev/null
sleep 1
cd "$PROJECT_DIR/frontend"
nohup npx vite --host 0.0.0.0 --port 5175 > "$LOG_DIR/frontend_dev.log" 2>&1 &
FRONTEND_PID=$!

echo "✅ Backend dev server started (PID: $BACKEND_PID, port: 4275)"
echo "✅ Vite dev server started (PID: $FRONTEND_PID, port: 5175)"
echo "📡 Frontend Dev URL: http://192.168.0.2:5175"
echo "🌐 Proxy URL: https://music.miong.me:9481"
