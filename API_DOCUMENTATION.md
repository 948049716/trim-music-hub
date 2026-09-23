# TRIM Music Hub - 后端 API 接口文档 (RESTful & SSE)

> **版本**：v1.2.0  
> **服务基础端口**：生产环境 `4175` / 开发环境 `3175`  
> **服务协议**：HTTP / SSE (Server-Sent Events)  
> **认证方式**：基于 HMAC-SHA256 签名的会话 Token，通过 HTTP 请求头 `x-auth-token: <token>` 或 Cookie `music_auth_token=<token>` 传递。  
> **核心架构**：基于 Node.js 原生标准库 + Python `db_ops.py` (直连 SQLite `music.db`) 混合驱动，所有接口皆为工程自定义 REST API。

---

## 目录
1. [系统与鉴权接口 (Auth & System)](#1-系统与鉴权接口-auth--system)
2. [实时状态与日志推流 (Status & SSE)](#2-实时状态与日志推流-status--sse)
3. [设置与目录管理 (Settings & Directories)](#3-设置与目录管理-settings--directories)
4. [全网检索与音源下载 (Search & Download)](#4-全网检索与音源下载-search--download)
5. [批量任务队列与控制 (Task Queue & Control)](#5-批量任务队列与控制-task-queue--control)
6. [飞牛歌单管理接口 (Playlists CRUD)](#6-飞牛歌单管理接口-playlists-crud)
7. [曲库检索与重复曲目管理 (Tracks & Duplicates)](#7-曲库检索与重复曲目管理-tracks--duplicates)
8. [第三方音乐平台账号与资产同步 (Music Accounts)](#8-第三方音乐平台账号与资产同步-music-accounts)
9. [封面静态资源服务 (Covers Proxy)](#9-封面静态资源服务-covers-proxy)

---

## 1. 系统与鉴权接口 (Auth & System)

### 1.1 服务健康检查
- **接口**：`GET /api/health`
- **认证**：公开无需 Token
- **返回**：
  ```json
  {
    "status": "ok",
    "timestamp": 1727081180000,
    "uptime": 3600.5
  }
  ```

### 1.2 管理员登录
- **接口**：`POST /api/auth/login`
- **认证**：公开无需 Token
- **请求体 (JSON)**：
  ```json
  {
    "password": "your_admin_password"
  }
  ```
- **返回 (JSON)**：
  ```json
  {
    "success": true,
    "token": "eyJ1c2VyIjoiYWRtaW4ifQ....signature",
    "user": "admin"
  }
  ```

### 1.3 校验当前登录状态
- **接口**：`GET /api/auth/me`
- **认证**：需要 Token
- **返回**：`{ "authenticated": true, "user": "admin" }`

### 1.4 退出登录
- **接口**：`POST /api/auth/logout`
- **认证**：需要 Token
- **返回**：`{ "success": true }`

### 1.5 获取系统用户列表 (飞牛/本地用户)
- **接口**：`GET /api/users`
- **认证**：需要 Token
- **说明**：通过 `db_ops.py` 查询飞牛 `user` 表与系统 Linux 用户。
- **返回**：
  ```json
  {
    "users": [
      { "id": 1000, "name": "948049716", "display_name": "Miong", "is_admin": true }
    ],
    "default_user": "948049716"
  }
  ```

---

## 2. 实时状态与日志推流 (Status & SSE)

### 2.1 实时事件流 (Server-Sent Events)
- **接口**：`GET /api/stream`
- **认证**：需要 Token (亦支持 URL 参数 `?token=...`)
- **说明**：建立长连接，单曲下载、批量队列、日志输出时毫秒级推送。
- **推流事件类型**：
  - `event: status`：任务状态环、进度、当前下载单曲
  - `event: log`：终端执行输出行
  - `event: queue`：下载队列与顺序变更通知

### 2.2 获取全局当前运行快照
- **接口**：`GET /api/status`
- **认证**：需要 Token
- **返回**：
  ```json
  {
    "status": "downloading",  // idle | downloading | parsing | error
    "progress": 45,
    "total": 10,
    "completed": 4,
    "failed": 0,
    "current_track": "告白气球 - 周杰伦",
    "speed": "2.4 MB/s"
  }
  ```

### 2.3 终端运行日志检索
- **接口**：`GET /api/logs?limit=200`
- **认证**：需要 Token
- **返回**：`{ "lines": ["[INFO] Downloading ...", "[SUCCESS] Injected flac metadata"] }`

### 2.4 子进程状态内部免密上报
- **接口**：`POST /api/update-status`
- **认证**：免密（仅限 127.0.0.1 本地脚本如 `music_manager.py` / `playlist_sync.py` 调用）
- **请求体**：
  ```json
  {
    "status": "downloading",
    "current_track": "歌名 - 歌手",
    "progress": 60,
    "total": 100
  }
  ```

---

## 3. 设置与目录管理 (Settings & Directories)

### 3.1 获取系统配置项
- **接口**：`GET /api/settings`
- **返回**：
  ```json
  {
    "download_source": "kw",
    "download_dir": "/vol2/1000/媒体/音乐",
    "concurrent_downloads": 5,
    "force_transcode": false,
    "available_sources": [
      { "id": "kw", "name": "酷我音乐", "desc": "高品质FLAC专线 · 推荐默认" },
      { "id": "kg", "name": "酷狗音乐", "desc": "海棠/星海SVIP线路" },
      { "id": "tx", "name": "QQ音乐", "desc": "长青/溯音专线" },
      { "id": "wy", "name": "网易云音乐", "desc": "163云音乐线路" },
      { "id": "auto", "name": "智能多源聚合", "desc": "酷我优先，故障自动回退" }
    ]
  }
  ```

### 3.2 保存配置项
- **接口**：`POST /api/settings`
- **请求体**：包含待修改的 `download_source`、`download_dir`、`concurrent_downloads` 等。

### 3.3 扫描与推荐音乐目录候选
- **接口**：`GET /api/settings/directories`
- **说明**：自动检索飞牛 NAS `/vol1`、`/vol2` 下挂载的媒体存储池。
- **返回**：`{ "directories": ["/vol2/1000/媒体/音乐", "/vol1/1000/Music"] }`

### 3.4 检验目录读写权限与有效性
- **接口**：`POST /api/settings/verify-directory`
- **请求体**：`{ "path": "/vol2/1000/媒体/音乐" }`
- **返回**：`{ "valid": true, "readable": true, "writable": true, "is_fnos_authorized": true }`

---

## 4. 全网检索与音源下载 (Search & Download)

### 4.1 全网多源检索单曲与查重标记
- **接口**：`GET /api/search/online?keyword=周杰伦&source=kw&page=1&limit=20`
- **认证**：需要 Token
- **核心逻辑**：抓取公网音源结果，同时调用 `db_ops.py` 的 `check_library()` 进行本地库查重。
- **返回**：
  ```json
  {
    "keyword": "周杰伦",
    "page": 1,
    "results": [
      {
        "id": "123456",
        "title": "晴天",
        "artist": "周杰伦",
        "album": "叶惠美",
        "duration": 269,
        "source": "kw",
        "has_flac": true,
        "is_local_exist": true,        // 飞牛本地曲库是否已有此歌
        "local_match": { "track_id": 8812, "quality": "FLAC" }
      }
    ]
  }
  ```

### 4.2 单曲立即下载与元数据归档
- **接口**：`POST /api/download/single`
- **请求体**：
  ```json
  {
    "song": "晴天",
    "artist": "周杰伦",
    "album": "叶惠美",
    "source": "kw",
    "quality": "flac",               // flac | 320k | 128k
    "target_user": "948049716"
  }
  ```
- **返回**：`{ "success": true, "task_id": "uuid-...", "message": "任务已加入队列" }`

---

## 5. 批量任务队列与控制 (Task Queue & Control)

### 5.1 解析外部歌单链接 (预检与查重)
- **接口**：`POST /api/tasks/parse-playlist`
- **说明**：输入网易云/QQ音乐链接，提取名称、封面原图，并完成本地库秒级查重。
- **请求体**：`{ "url": "https://music.163.com/playlist?id=xxx" }`
- **返回**：
  ```json
  {
    "playlist_name": "私藏华语精选",
    "cover_url": "http://p1.music.126.net/...",
    "total_count": 50,
    "exist_count": 20,
    "missing_count": 30,
    "tracks": [
      { "title": "晴天", "artist": "周杰伦", "is_exist": true },
      { "title": "搁浅", "artist": "周杰伦", "is_exist": false }
    ]
  }
  ```

### 5.2 启动批量同步/导入任务
- **接口**：`POST /api/tasks/start`
- **请求体**：
  ```json
  {
    "url": "https://music.163.com/playlist?id=xxx",
    "target_mode": "user",           // user | public
    "target_user": "948049716",
    "quality": "flac",
    "source": "kw"
  }
  ```

### 5.3 获取当前下载排队队列
- **接口**：`GET /api/tasks/queue`
- **返回**：`{ "active": [...], "pending": [...], "completed": [...] }`

### 5.4 调整队列任务优先级/排序
- **接口**：`POST /api/tasks/reorder`
- **请求体**：`{ "task_ids": ["uuid-1", "uuid-2", "uuid-3"] }`

### 5.5 取消指定任务
- **接口**：`POST /api/tasks/cancel`
- **请求体**：`{ "task_id": "uuid-1" }`

### 5.6 恢复/断点续传中断的任务
- **接口**：`POST /api/tasks/resume`
- **请求体**：`{ "task_id": "uuid-1" }`

### 5.7 清除已完成任务
- **接口**：`POST /api/tasks/clear-completed`

### 5.8 紧急停止当前正在执行的全局任务
- **接口**：`POST /api/tasks/stop`

---

## 6. 飞牛歌单管理接口 (Playlists CRUD)

> **底层映射**：直接读写飞牛 SQLite 数据库 `playlist` 及 `playlist_track_link` 表。

### 6.1 获取所有歌单列表
- **接口**：`GET /api/playlists`
- **返回**：
  ```json
  {
    "playlists": [
      {
        "id": 12,
        "guid": "a1b2c3d4...",
        "name": "车载无损专区",
        "track_count": 45,
        "user_id": 1000,
        "user_name": "948049716",
        "cover_guid": "e5f6g7h8..."
      }
    ]
  }
  ```

### 6.2 获取指定歌单内的曲目列表
- **接口**：`GET /api/playlists/tracks?playlist_id=12`
- **返回**：`{ "tracks": [{ "id": 101, "title": "晴天", "artist": "周杰伦", "album": "叶惠美", "duration": 269, "path": "/vol2/1000/媒体/音乐/周杰伦/周杰伦 - 晴天.flac" }] }`

### 6.3 歌单重命名
- **接口**：`POST /api/playlists/rename`
- **请求体**：`{ "playlist_id": 12, "name": "新歌单名" }`

### 6.4 歌单转让/归属用户修改
- **接口**：`POST /api/playlists/update-users`
- **请求体**：`{ "playlist_id": 12, "target_user_id": 1000 }`

### 6.5 从歌单中移除指定曲目
- **接口**：`POST /api/playlists/remove-tracks`
- **请求体**：`{ "playlist_id": 12, "track_ids": [101, 102] }`

### 6.6 删除歌单 (支持联动物理删除)
- **接口**：`POST /api/playlists/delete`
- **说明**：若 `delete_files=true`，会自动检测该曲目是否被其他歌单引用，无其他引用时直接删除 NAS 上的磁盘文件及对应 `.lrc`。
- **请求体**：
  ```json
  {
    "playlist_id": 12,
    "delete_files": false
  }
  ```

---

## 7. 曲库检索与重复曲目管理 (Tracks & Duplicates)

### 7.1 曲库全量曲目搜索与分页检索
- **接口**：`GET /api/tracks/search?keyword=周杰伦&page=1&limit=50`
- **返回**：`{ "total": 120, "page": 1, "tracks": [...] }`

### 7.2 单个/指定曲目删除
- **接口**：`POST /api/tracks/delete`
- **请求体**：`{ "track_id": 101, "delete_file": true }`

### 7.3 扫描曲库重复歌曲
- **接口**：`GET /api/tracks/duplicates`
- **说明**：通过算法匹配相似歌名与歌手，返回可能冗余的重复版本（如不同码率、同曲异名）。
- **返回**：
  ```json
  {
    "duplicates": [
      {
        "group_key": "周杰伦_晴天",
        "tracks": [
          { "id": 101, "title": "晴天", "bitrate": 980, "format": "flac", "path": "..." },
          { "id": 204, "title": "晴天", "bitrate": 320, "format": "mp3", "path": "..." }
        ]
      }
    ]
  }
  ```

### 7.4 批量删除曲目
- **接口**：`POST /api/tracks/batch-delete`
- **请求体**：`{ "track_ids": [204, 305], "delete_files": true }`

---

## 8. 第三方音乐平台账号与资产同步 (Music Accounts)

### 8.1 网易云音乐：生成扫码登录二维码
- **接口**：`POST /api/music-accounts/netease/qr/create`
- **返回**：
  ```json
  {
    "unikey": "xxxx-xxxx",
    "qr_url": "https://music.163.com/...",
    "qr_img_base64": "data:image/png;base64,...."
  }
  ```

### 8.2 网易云音乐：轮询扫码授权状态
- **接口**：`POST /api/music-accounts/netease/qr/check`
- **请求体**：`{ "unikey": "xxxx-xxxx" }`
- **返回状态码**：
  - `801`：等待扫码中
  - `802`：已扫码，等待手机端授权确认
  - `803`：授权成功（已自动提取 Cookie 并持久化写入 `data/music_accounts.json`）
  - `800`：二维码已过期

### 8.3 获取已登录绑定的音乐账号列表
- **接口**：`GET /api/music-accounts`
- **返回**：
  ```json
  {
    "accounts": [
      { "platform": "netease", "nickname": "Miong", "avatar_url": "...", "status": "active" },
      { "platform": "qq", "nickname": "Miong", "avatar_url": "...", "status": "active" }
    ]
  }
  ```

### 8.4 拉取第三方账号的云端歌单资产
- **接口**：`GET /api/music-accounts/:platform/playlists`
- **示例**：`GET /api/music-accounts/netease/playlists`
- **返回**：
  ```json
  {
    "playlists": [
      { "id": "12345", "name": "我喜欢的音乐", "track_count": 320, "cover_url": "..." },
      { "id": "67890", "name": "日落精选", "track_count": 28, "cover_url": "..." }
    ]
  }
  ```

### 8.5 一键导入第三方账号歌单
- **接口**：`POST /api/music-accounts/:platform/import`
- **请求体**：`{ "playlist_ids": ["12345"], "target_user": "948049716", "mode": "merge" }`

---

## 9. 封面静态资源服务 (Covers Proxy)

### 9.1 读取封面图片
- **接口**：`GET /api/covers/:type/:guid?size=160`
- **参数说明**：
  - `:type`：`playlist` | `track` | `album` | `artist`
  - `:guid`：32位十六进制散列值 (如 `a1b2c3d4e5f6...`)
  - `size`：可选尺寸 `120` | `160` | `400` | `600` | `800` (默认 `160`)
- **说明**：优先从飞牛封面池分片路径（`/var/apps/trim.music/meta/cover/:type/:guid[0:2]/:guid_w160.jpg`）读取；开发环境未命中时自动放行代理。
- **返回**：图片二进制流（`Content-Type: image/jpeg` 或 `image/webp`，附带 `Cache-Control: public, max-age=86400, immutable`）。
