#!/bin/bash
export PATH="/vol1/@appcenter/nodejs_v24/bin:$PATH"
PROJECT_DIR="/vol1/1000/Project/trim-music-hub"
LOG_DIR="$PROJECT_DIR/data/logs"
mkdir -p "$LOG_DIR"

echo "=== Starting TRIM Music Hub Frontend Dev Server ==="

# 清理历史遗留的开发后端 PID 与进程
BACKEND_PID_FILE="$LOG_DIR/backend_dev.pid"
if [ -f "$BACKEND_PID_FILE" ]; then
  OLD_BACKEND_PID=$(cat "$BACKEND_PID_FILE" 2>/dev/null)
  if [ -n "$OLD_BACKEND_PID" ] && kill -0 "$OLD_BACKEND_PID" 2>/dev/null; then
    kill "$OLD_BACKEND_PID" 2>/dev/null
  fi
  rm -f "$BACKEND_PID_FILE"
fi

# 检查正式后端服务 (端口 4175)
if ! ss -tulpn | grep -q ':4175 '; then
  echo "⚠️ 警告: 正式后端 (端口 4175) 未检测到监听，尝试检查系统服务状态..."
  systemctl status music-monitor.service --no-pager 2>/dev/null || true
else
  echo "✅ 正式后端服务就绪 (端口: 4175, root 运行)"
fi

# 停止可能存在的旧 Vite 实例 (端口 5175)
pkill -f "vite.*5175" 2>/dev/null
sleep 1

cd "$PROJECT_DIR/frontend"
nohup npx vite --host 0.0.0.0 --port 5175 > "$LOG_DIR/frontend_dev.log" 2>&1 &
FRONTEND_PID=$!

echo "✅ Vite dev server started (PID: $FRONTEND_PID, port: 5175)"
echo "📡 Frontend Dev URL: http://192.168.0.2:5175"
echo "🌐 Proxy URL: https://music.miong.me:9481"
echo "🔗 Backend Target: http://127.0.0.1:4175 (正式服务)"
