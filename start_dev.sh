#!/bin/bash
export PATH="/vol1/@appcenter/nodejs_v24/bin:$PATH"
PROJECT_DIR="/vol1/1000/Project/trim-music-hub"
LOG_DIR="$PROJECT_DIR/data/logs"
mkdir -p "$LOG_DIR"

echo "=== Starting TRIM Music Hub Full-Stack Dev Environment ==="

# 1. 清理旧的开发后端进程
BACKEND_PID_FILE="$LOG_DIR/backend_dev.pid"
if [ -f "$BACKEND_PID_FILE" ]; then
  OLD_BACKEND_PID=$(cat "$BACKEND_PID_FILE" 2>/dev/null)
  if [ -n "$OLD_BACKEND_PID" ] && kill -0 "$OLD_BACKEND_PID" 2>/dev/null; then
    echo "Stopping existing dev backend (PID: $OLD_BACKEND_PID)..."
    sudo kill "$OLD_BACKEND_PID" 2>/dev/null || true
  fi
  rm -f "$BACKEND_PID_FILE"
fi
sudo pkill -f "node.*server.mjs.*3175" 2>/dev/null || true
sleep 1

# 2. 启动独立开发后端 (端口 3175, 开启 --watch 热监听与 .env 环境变量注入)
echo "🚀 启动独立开发后端 (端口: 3175, 开启 --watch 热重载)..."
cd "$PROJECT_DIR"
sudo nohup /vol1/@appcenter/nodejs_v24/bin/node --watch --env-file="$PROJECT_DIR/.env" "$PROJECT_DIR/server.mjs" > "$LOG_DIR/backend_dev.log" 2>&1 &
echo $! > "$BACKEND_PID_FILE"

# 等待后端就绪
for i in {1..10}; do
  if ss -tulpn | grep -q ':3175 '; then
    echo "✅ 独立开发后端启动成功 (端口: 3175)"
    break
  fi
  sleep 0.5
done

# 3. 清理旧的 Vite 前端进程
FRONTEND_PID_FILE="$LOG_DIR/frontend_dev.pid"
if [ -f "$FRONTEND_PID_FILE" ]; then
  OLD_FRONTEND_PID=$(cat "$FRONTEND_PID_FILE" 2>/dev/null)
  if [ -n "$OLD_FRONTEND_PID" ] && kill -0 "$OLD_FRONTEND_PID" 2>/dev/null; then
    kill "$OLD_FRONTEND_PID" 2>/dev/null || true
  fi
  rm -f "$FRONTEND_PID_FILE"
fi
pkill -f "vite.*5175" 2>/dev/null || true
sleep 1

# 4. 启动 Vite 前端开发服务器 (端口 5175, 支持 HMR 热更新)
echo "🚀 启动前端 Vite 开发服务器 (端口: 5175, 代理至 3175)..."
cd "$PROJECT_DIR/frontend"
nohup /vol1/@appcenter/nodejs_v24/bin/npx vite --host 0.0.0.0 --port 5175 > "$LOG_DIR/frontend_dev.log" 2>&1 &
echo $! > "$FRONTEND_PID_FILE"
sleep 1

echo "=========================================================="
echo "🎉 全栈开发环境启动完成！"
echo "🌐 前端公网入口: https://musicdev.miong.me:9481"
echo "📡 前端局域网入口: http://192.168.0.2:5175"
echo "🔗 独立后端接口: http://192.168.0.2:3175"
echo "🛡️ 正式生产服务: https://music.miong.me:9481 (端口 4175 完全隔离保持运行)"
echo "=========================================================="
