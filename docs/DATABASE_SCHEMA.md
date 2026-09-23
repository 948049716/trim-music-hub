# 🗄️ 飞牛音乐 (fnOS Music) 数据库 Schema 与跨设备开发指南

> 本文档完整整理了飞牛 NAS 官方「飞牛音乐 (`trim.music`)」底层 SQLite 数据库 (`/usr/local/apps/@appdata/trim.music/db/music.db`) 的表结构、实体关联关系，以及在**非飞牛 NAS 环境（如异地电脑、本地 Mac/Windows 开发机）**下的 Mock 数据库初始化与开发方案。

- **原始 DDL SQL 文件**：[`docs/fnos_music_schema.sql`](./fnos_music_schema.sql)（含飞牛官方完整建表语句、索引及原版中文注释）
- **数据库引擎**：SQLite 3 (`WAL` 并发模式)
- **项目桥接层**：[`db_ops.py`](../db_ops.py)

---

## 一、 异地 / 另一台电脑离线开发指南

当你在另一台电脑（无飞牛 NAS 环境、无法直连 `/usr/local/apps/@appdata/trim.music/db/music.db`）为后端增加新功能时，可以通过项目内置的 `docs/fnos_music_schema.sql` 一键生成本地开发数据库：

### 1. 初始化本地空数据库（含完整 23 张表与索引）
```bash
# 在项目根目录下执行：使用官方 Schema 创建本地 SQLite 数据库文件
sqlite3 ./data/mock_music.db < docs/fnos_music_schema.sql
```

### 2. 指定环境变量启动后端服务
`db_ops.py` 与 `server.mjs` 原生支持通过 `FNOS_DB_PATH` 环境变量覆盖默认数据库路径：
```bash
# 在 .env 中配置或直接命令行指定：
FNOS_DB_PATH=./data/mock_music.db
MUSIC_DIR=./data/mock_music_files

# 启动开发栈
bash start_dev.sh
# 或单独启动后端监听
FNOS_DB_PATH=./data/mock_music.db node --watch server.mjs
```

---

## 二、 数据库表全景分类速览（共 23 张表）

### 1. 核心曲库与音频资产域（最常读写）

| 表名 | 核心用途 | 关键字段与关联说明 |
| :--- | :--- | :--- |
| **`audio_file`** | **物理音频文件表** | `id` (PK), `shared_library_id` (关联媒体库), `path` (UNIQUE 物理绝对路径), `name`, `suffix` (如 `.flac`), `size` (字节), `hash`, `duration_ms` (毫秒), `bitrate`, `sample_rate`, `bit_depth`, `channel`, `container`, `codec`, `tag_payload` (JSON 标签), `is_physical_file_deleted` (0=正常, 1=物理文件已删) |
| **`track`** | **曲目元数据核心表** | `id` (PK), `guid` (UNIQUE 全局ID), `audio_file_id` (FK -> `audio_file.id`), `shared_library_id`, `title` (歌名), `title_latin_full` (全拼排序), `album_id` (FK -> `album.id`), `cover_guid` (封面缓存UUID), `year`, `disc_no`, `track_no`, `isrc`, `duration_ms`, `metadata_mode` (`1`=local, `2`=cloud), `cloud_scrape_status` (`0`=none, `1`=pending, `2`=success, `3`=failed, `4`=not_found), `is_audio_file_deleted` (`0`/`1`), `is_admin_deleted` (`0`/`1`) |
| **`artist`** | **歌手 / 艺术家表** | `id` (PK), `guid` (UNIQUE), `name` (歌手名), `name_latin_full` (拼音), `cover_guid` (歌手头像UUID), `metadata_mode` (`1`=local, `2`=cloud), `metadata_cloud_provider` (`1`=official), `metadata_cloud_ref_id` |
| **`album`** | **专辑表** | `id` (PK), `guid` (UNIQUE), `name` (专辑名), `name_latin_full` (拼音), `cover_guid` (专辑封面UUID), `release_date` (如 `2026-02-02`), `total_track`, `barcode`, `metadata_mode` |
| **`track_artist`** | **曲目-歌手多对多关联** | `id` (PK), `track_id` (FK -> `track.id`), `artist_id` (FK -> `artist.id`), `artist_order` (歌手排序，0为主歌手)。唯一约束：`(track_id, artist_id)` |
| **`album_artist`** | **专辑-歌手多对多关联** | `id` (PK), `album_id` (FK -> `album.id`), `artist_id` (FK -> `artist.id`), `artist_order`。唯一约束：`(album_id, artist_id)` |
| **`genre`** | **音乐风格 / 流派表** | `id` (PK), `guid` (UNIQUE), `name` (流派名称), `name_latin_full`, `cover_guid`, `metadata_mode` |
| **`track_genre`** | **曲目-流派多对多关联** | `id` (PK), `track_id` (FK -> `track.id`), `genre_id` (FK -> `genre.id`)。唯一约束：`(track_id, genre_id)` |
| **`lyric`** | **歌词存储与映射表** | `id` (PK), `guid` (UNIQUE), `track_id` (FK -> `track.id`), `source` (`1`=内嵌 embedded, `2`=同目录 `.lrc` 伴随文件 sidecar, `3`=云端刮削 scraped, `4`=用户手动关联 user_linked), `stored_guid` (提取后在本地缓存目录的存储文件名) |

---

### 2. 歌单、红心收藏与播放历史域

| 表名 | 核心用途 | 关键字段与关联说明 |
| :--- | :--- | :--- |
| **`playlist`** | **用户自建 / 导入歌单表** | `id` (PK), `guid` (UNIQUE 全局唯一ID), `name` (歌单名称), `cover_guid` (歌单封面UUID，存于 `/vol1/@appmeta/trim.music/cover/`), `user_id` (FK -> `user.id`，歌单所属用户) |
| **`playlist_track`** | **歌单内曲目关联表** | `id` (PK), `user_id` (冗余字段，所属用户), `playlist_id` (FK -> `playlist.id`), `track_id` (FK -> `track.id`), `added_at` (加入时间，用于歌单内曲目排序)。唯一约束：`(playlist_id, track_id)` |
| **`favorite_track`** | **我喜欢的音乐 (红心收藏)** | `id` (PK), `user_id` (FK -> `user.id`), `track_id` (FK -> `track.id`), `created_at`。唯一约束：`(user_id, track_id)` |
| **`play_history`** | **播放历史与播放次数表** | `id` (PK), `user_id` (FK -> `user.id`), `track_id` (FK -> `track.id`), `play_count` (累计播放次数，默认 1), `created_at`, `updated_at`。唯一约束：`(user_id, track_id)` |

---

### 3. 用户、认证与共享媒体库权限域

| 表名 | 核心用途 | 关键字段与关联说明 |
| :--- | :--- | :--- |
| **`user`** | **飞牛音乐用户表** | `id` (PK), `guid` (UNIQUE), `name` (用户名，如 `948049716` / `admin`), `name_latin_full`, `password`, `role` (`admin`=管理员, `member`=普通用户), `created_by` (`oauth`=NAS统一授权, `manual`=手动创建), `status` (`active`=正常, `deleted`=已删除), `shared_library_access_mode` (`none` / `all` / `custom`), `last_accessed_at` |
| **`user_oauth`** | **NAS 统一账号绑定表** | `id` (PK), `user_id` (FK -> `user.id`), `user_deleted` (`0`/`1`), `oauth_provider` (固定如 `trim-nas`), `oauth_user_id` (NAS 底层 UID), `oauth_user_name` |
| **`user_token`** | **多端登录会话 Token 表** | `id` (PK), `user_id` (FK -> `user.id`), `token` (UNIQUE), `device_id` (设备标识), `expired_at`, `is_auth_login` |
| **`shared_library`** | **音乐媒体库文件夹配置** | `id` (PK), `guid` (UNIQUE), `path` (UNIQUE 物理挂载目录，如 `/vol2/1000/媒体/音乐`), `metadata_preference`, `auto_download_lyric` (`1`=自动下载歌词), `content_last_changed_at` |
| **`shared_library_member`** | **媒体库用户访问权限表** | `id` (PK), `shared_library_id` (FK -> `shared_library.id`), `user_id` (FK -> `user.id`)。唯一约束：`(shared_library_id, user_id)` |

---

### 4. 用户偏好与系统状态域

| 表名 | 核心用途 | 关键字段与关联说明 |
| :--- | :--- | :--- |
| **`user_track_lyric_preference`** | **用户单曲首选歌词绑定** | `user_id`, `track_id`, `lyric_id` (关联 `lyric.id`，记录用户上次选定的歌词版本) |
| **`user_track_lyric_offset`** | **歌词时间轴偏移微调** | `user_id`, `track_id`, `lyric_id`, `offset_ms` (毫秒偏移：正数=提前，负数=延后) |
| **`user_sorting_preference`** | **列表排序偏好记忆** | `user_id`, `sort_id` (视图标识), `sorting` (排序规则 JSON/文本) |
| **`app_state`** | **应用全局状态键值表** | `k` (UNIQUE，如 `initialized`), `v` (如 `true`), `payload` (扩展 JSON) |
| **`app_hook`** | **系统内部 Hook 键值表** | `id`, `key`, `value`, `created_at`, `updated_at` |

---

## 三、 核心多表查询 SQL 范例

### 1. 查询完整曲目信息（联查歌名、合并歌手、专辑、物理文件路径与格式）
```sql
SELECT
    t.id AS track_id,
    t.guid AS track_guid,
    t.title,
    GROUP_CONCAT(ar.name, ' / ') AS artist_name,
    al.name AS album_name,
    af.path AS file_path,
    af.suffix,
    af.size,
    af.bitrate,
    af.sample_rate,
    af.bit_depth,
    t.duration_ms,
    t.cover_guid
FROM track t
JOIN audio_file af ON t.audio_file_id = af.id
LEFT JOIN album al ON t.album_id = al.id
LEFT JOIN track_artist ta ON t.id = ta.track_id
LEFT JOIN artist ar ON ta.artist_id = ar.id
WHERE t.is_audio_file_deleted = 0
  AND t.is_admin_deleted = 0
  AND af.is_physical_file_deleted = 0
GROUP BY t.id
ORDER BY t.created_at DESC;
```

### 2. 查询指定歌单内的全部曲目（按加入时间排序）
```sql
SELECT
    pt.id AS link_id,
    pt.added_at,
    t.id AS track_id,
    t.title,
    GROUP_CONCAT(ar.name, ' / ') AS artist_name,
    al.name AS album_name,
    af.path AS file_path
FROM playlist_track pt
JOIN track t ON pt.track_id = t.id
JOIN audio_file af ON t.audio_file_id = af.id
LEFT JOIN album al ON t.album_id = al.id
LEFT JOIN track_artist ta ON t.id = ta.track_id
LEFT JOIN artist ar ON ta.artist_id = ar.id
WHERE pt.playlist_id = ?
  AND t.is_audio_file_deleted = 0
GROUP BY pt.id
ORDER BY pt.added_at ASC;
```

### 3. 封面缓存目录机制 (`cover_guid`)
- 数据库中 `track.cover_guid`、`album.cover_guid`、`artist.cover_guid`、`playlist.cover_guid` 存储的均是 32 位 UUID 字符串（如 `a1b2c3d4...`）。
- 对应宿主机物理目录为：`/vol1/@appmeta/trim.music/cover/`（容器内挂载为 `/app/cover/`）。
- 每个 `cover_guid` 对应一组多尺寸 WebP 图像文件：
  - `<cover_guid>`（原图）
  - `<cover_guid>_w160.webp`（160px 列表缩略图）
  - `<cover_guid>_w400.webp`（400px 卡片封面图）
  - `<cover_guid>_w600.webp`（600px 高清播放页封面图）
