#!/bin/bash
set -e

PROJECT_DIR="/vol1/1000/Project/trim-music-hub"
PROD_DOCKER_DIR="/vol1/1000/docker/trim-music-hub"

echo "=========================================================="
echo "🚀 TRIM Music Hub 生产环境安全发布流水线"
echo "=========================================================="

# 1. 确保在正确的项目目录
cd "$PROJECT_DIR"

# 2. 构建生产 Docker 镜像 (包含 Vite 前端打包 + 后端 Node.js + Python/FFmpeg 环境)
echo "📦 [1/3] 开始构建生产 Docker 镜像 (trim-music-hub:latest)..."
docker build -t trim-music-hub:latest "$PROJECT_DIR"

# 3. 部署并平滑重建生产容器
echo "🔄 [2/3] 部署并平滑重建生产容器..."
cd "$PROD_DOCKER_DIR"
docker compose up -d --force-recreate

# 4. 健康检查探针探测
echo "🩺 [3/3] 正在探测生产容器健康状态 (http://127.0.0.1:4175/api/health)..."
HEALTHY=0
for i in {1..20}; do
  STATUS=$(curl -s http://127.0.0.1:4175/api/health 2>/dev/null | grep -o '"ok":true' || true)
  if [ -n "$STATUS" ]; then
    HEALTHY=1
    break
  fi
  sleep 1
done

if [ "$HEALTHY" -eq 1 ]; then
  echo "=========================================================="
  echo "🎉 生产环境部署成功并已恢复就绪！"
  echo "🛡️ 正式服务入口: https://music.miong.me:9481 (端口 4175)"
  echo "🧪 开发独立入口: https://musicdev.miong.me:9481 (端口 5175/3175 互不干扰)"
  echo "=========================================================="
else
  echo "⚠️ 生产容器未在预期时间内通过健康检查，请检查容器日志: docker logs trim-music-hub"
  exit 1
fi
