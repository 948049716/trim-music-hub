#!/bin/bash
PROJECT_DIR="/vol1/1000/Project/trim-music-hub"
LOG_DIR="$PROJECT_DIR/data/logs"

echo "=== Stopping TRIM Music Hub Dev Environment ==="

# 停止开发后端 (3175)
BACKEND_PID_FILE="$LOG_DIR/backend_dev.pid"
if [ -f "$BACKEND_PID_FILE" ]; then
  PID=$(cat "$BACKEND_PID_FILE" 2>/dev/null)
  if [ -n "$PID" ]; then
    sudo kill "$PID" 2>/dev/null || true
  fi
  rm -f "$BACKEND_PID_FILE"
fi
sudo pkill -f "node.*server.mjs.*3175" 2>/dev/null || true

# 停止开发前端 (5175)
FRONTEND_PID_FILE="$LOG_DIR/frontend_dev.pid"
if [ -f "$FRONTEND_PID_FILE" ]; then
  PID=$(cat "$FRONTEND_PID_FILE" 2>/dev/null)
  if [ -n "$PID" ]; then
    kill "$PID" 2>/dev/null || true
  fi
  rm -f "$FRONTEND_PID_FILE"
fi
pkill -f "vite.*5175" 2>/dev/null || true

echo "✅ 开发环境服务已全部停止。"
