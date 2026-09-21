# TRIM Music Hub - Dockerfile (Multi-stage Build)
# Stage 1: Build modern frontend SPA (Vite + Vue 3 + TypeScript)
FROM node:24-bookworm-slim AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package.json ./
RUN npm config set registry https://registry.npmmirror.com && npm install

COPY frontend/ ./
RUN npm run build

# Stage 2: Final lightweight runtime container
FROM node:24-bookworm-slim

LABEL maintainer="TRIM Music Hub"
LABEL description="fnOS (飞牛 NAS) 音乐导入、单曲搜索下载与曲库管理中枢 (Vue 3 + Node.js 24 + Python 3)"

ENV DEBIAN_FRONTEND=noninteractive \
    NODE_ENV=production \
    PORT=4175 \
    HOST=0.0.0.0 \
    MUSIC_DIR=/media/music \
    FNOS_DB_PATH=/app/db/music.db \
    DATA_DIR=/app/data \
    PUID=1000 \
    PGID=1000 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# Install required system tools (Python3, FLAC/metaflac, FFmpeg, curl)
RUN (sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list 2>/dev/null || true) && \
    apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    flac \
    ffmpeg \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create necessary mount points
RUN mkdir -p /media/music /app/db /app/data

# Copy backend dependencies & install
COPY package.json package-lock.json ./
RUN npm config set registry https://registry.npmmirror.com && npm install --omit=dev

# Copy backend files
COPY server.mjs db_ops.py ./
COPY scripts/ ./scripts/
COPY public/ ./public/

# Copy built modern frontend from builder stage
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Ensure execution permissions on scripts
RUN chmod +x db_ops.py scripts/*.py

EXPOSE 4175

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:4175/api/health || exit 1

CMD ["node", "server.mjs"]
