# 🎵 TRIM Music Hub (飞牛音乐中枢)

> 专为 **飞牛 NAS (fnOS)** 深度定制的无损音乐搜索下载、第三方歌单极速同步与底层曲库可视化管理中心。

---

## ✨ 核心特性

- **🔍 单曲即搜即下（内置音源）**：输入歌名或歌手，全网检索正版高品质音源，无须依赖任何外部复杂服务。
- **⚡ 飞牛曲库秒级深度查重**：搜歌结果自动比对飞牛官方数据库与物理存储目录。若本地已收录，自动标明路径并锁定禁止重复下载；若未收录，支持一键下载。
- **🎛️ 多音质智能切换**：组合式下载按钮，默认精选 **FLAC 24-bit 无损**，并支持下拉切换 **320K (高品)** 或 **128K (标准)**。
- **🏷️ 全自动元数据与双重歌词**：自动注入 ID3/Vorbis 标签（歌名/歌手/专辑/年份）；原版高清封面与歌手写真兜底内嵌；自动抓取高精度滚动歌词，既内嵌音频，同时在同级目录生成标准 `.lrc` 文件，车载与第三方播放器完美兼容。
- **📋 第三方歌单批量导入**：支持粘贴 **网易云音乐** 或 **QQ 音乐** 歌单链接，一键批量解析、自动查重去重（已有曲目跳过下载但全量入单）、抓取无损、自动生成 `.m3u8` 播放列表并直写飞牛官方音乐库。
- **💽 直通飞牛底座数据库**：可视化查看所有公共歌单与个人歌单，支持在线查看曲目、歌单重命名、删除歌单，支持全库检索 6,000+ 首歌曲并一键彻底清理物理文件。
- **🚀 极致无感局部重绘**：彻底告别浏览器全局刷新与原生弹框，所有删除、重命名、下载状态均采用现代化 Toast 与 DOM 局部增量渲染。
- **📊 玻璃拟态大屏与实时推流**：内置黑胶旋转动效、总体进度环、耗时预估与 SSE 零延迟实时控制台终端日志流。
- **📖 完整数据库文档与跨机开发支持**：提供飞牛底层完整 23 张数据表结构 [`docs/DATABASE_SCHEMA.md`](docs/DATABASE_SCHEMA.md) 与官方 DDL [`docs/fnos_music_schema.sql`](docs/fnos_music_schema.sql)，支持任意离线机器一键初始化 Mock 数据库无缝联调开发。

---

## 🛠️ 必须配置的 2 个核心目录

| 配置项 | 容器内固定路径 | 宿主机对应路径说明 |
| :--- | :--- | :--- |
| **本地音乐存储目录** | `/media/music` | **【必选】** 您 NAS 上存放音乐的真实目录，例如 `/vol1/1000/Music` 或 `/vol2/1000/媒体/音乐` |
| **飞牛音乐官方数据库** | `/app/db` | **【必选】** 飞牛系统安装「飞牛音乐」App 后的数据库目录，固定为 `/usr/local/apps/@appdata/trim.music/db` |

---

## 🚀 方式一：Docker Compose 一键部署（强烈推荐）

### 1. 克隆或下载本项目
```bash
git clone https://github.com/your-username/trim-music-hub.git
cd trim-music-hub
```

### 2. 配置环境变量
复制环境配置模板：
```bash
cp .env.example .env
```
使用文本编辑器修改 `.env` 中的 `MUSIC_PATH`（指向您 NAS 上的真实音乐路径），例如：
```env
MUSIC_PATH=/vol1/1000/Music
FNOS_DB_DIR=/usr/local/apps/@appdata/trim.music/db
PORT=4175
PUID=1000
PGID=1000
DEFAULT_USER=admin
```

### 3. 构建并启动容器
```bash
docker compose up -d --build
```
启动成功后，浏览器打开 `http://<飞牛NAS的局域网IP>:4175` 即可直接使用！

---

## 🖥️ 方式二：飞牛 NAS 容器管理页面（Web UI）部署

如果您习惯在飞牛系统自带的 **「Docker」** 图形界面中创建：

1. 打开飞牛桌面上的 **Docker** 应用 -> **Compose** -> **新增项目**。
2. 输入项目名（如 `trim-music-hub`）。
3. 在配置文本框中粘贴以下内容（**请注意修改第 1 个卷映射为您自己的音乐目录**）：

```yaml
services:
  trim-music-hub:
    image: trim-music-hub:latest
    build:
      context: https://github.com/your-username/trim-music-hub.git
    container_name: trim-music-hub
    restart: unless-stopped
    ports:
      - "4175:4175"
    environment:
      - TZ=Asia/Shanghai
      - PORT=4175
      - PUID=1000
      - PGID=1000
      - DEFAULT_USER=admin
      - MUSIC_DIR=/media/music
      - FNOS_DB_PATH=/app/db/music.db
      - FNOS_COVER_DIR=/app/cover
    volumes:
      # 【必须修改】冒号左边修改为您 NAS 上的实际音乐目录
      - /vol1/1000/Music:/media/music:rw
      # 【无需修改】飞牛官方音乐应用数据库目录
      - /usr/local/apps/@appdata/trim.music/db:/app/db:rw
      # 飞牛音乐已刮削封面缓存（只读）
      - /vol1/@appmeta/trim.music/cover:/app/cover:ro
      # 数据持久化目录
      - ./data:/app/data:rw
```
4. 点击 **「立即构建并启动」**。

---

## 🌐 Nginx 反向代理配置（公网与域名访问）

如需将本中心通过二级域名（例如 `music.yourdomain.com`）发布到公网，请在 Nginx 的 `server` 块中配置如下（**务必关闭代理缓冲以保证 SSE 日志实时流畅推送**）：

```nginx
server {
    listen 80;
    listen 443 ssl;
    server_name music.yourdomain.com;

    location / {
        proxy_pass         http://127.0.0.1:4175;
        proxy_http_version 1.1;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;

        # 核心：关闭缓冲以支持 SSE 0 延迟实时控制台与进度推送
        proxy_buffering    off;
        proxy_cache        off;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
```

---

## 🧠 歌曲去重与防重复下载匹配规则 (Deduplication Rules)

为防止重复下载占用磁盘空间并确保歌单同步的精准度，TRIM Music Hub 采用了基于 **飞牛官方数据库 (SQLite) + 物理文件系统兜底** 的智能查重引擎，核心规则如下：

### 1. 歌手双向泛化与别名归一化 (Artist Aliases & Bi-directional Matching)
- **多歌手自动拆解**：遇到合唱或 Featuring（如 `蔡依林 / 陶喆`、`周杰伦 feat. 阿信`、`A & B`），系统自动拆解为独立艺人词元，只要匹配其中任一有效歌手即可命中。
- **中英文混合与别名前缀拆解**：针对如 `G.E.M.邓紫棋`、`周杰伦 Jay Chou` 等艺人，系统自动提取中英文独立成分（如 `邓紫棋`、`G.E.M.`、`GEM`），支持艺人跨平台写法互认。
- **标点与空格符号清洗**：自动去除圆点 `.`、连字符 `-`、空格及下划线，避免因 `G.E.M.` vs `GEM`、`S.H.E` vs `SHE` 导致字符串匹配脱靶。
- **双向互相包含验证**：全面突破传统单向 SQL 匹配局限，即使云端提供长全称（`G.E.M.邓紫棋`）而本地库只记录简写（`邓紫棋`），或反之本地库记录全称而云端为简写，均能精准互认。
- **物理路径歌手辅助匹配**：当数据库内艺人标签不完善时，系统会自动将提取的艺人特征与音频物理路径（如 `/音乐/GEM 邓紫棋 合集/...`）进行交叉印证。

### 2. 歌名净化与版本容错 (Title Cleaning & Version Tolerance)
- **括号后缀智能净化**：自动剥离各类全角/半角圆括号与方括号，如 `(Live)`、`（粤语版）`、`[2024 Remaster]`、`【经典版】`，提取纯正核心歌名。
- **版本后缀过滤**：自动识别并剥离歌名后带有的短横线后缀（如 `- Live`、`- 2023 Remaster`、`- 伴奏` 等）。
- **防翻唱误杀机制**：严格遵循“歌名 + 歌手关联”双重校验，绝不会单凭相同歌名武断判定重复，保护不同歌手的同名原创或翻唱曲目。

### 3. 多版本智能评分与优选机制 (Scoring & Ranking)
当库中存在同一歌曲的多个录音或格式副本时，引擎采用加权评分挑选最优本地对应文件：
- **物理文件在盘真实有效**：`+20 分`（彻底排除已删除但数据库残留的无效脏记录）
- **数据库无删除标记**（`is_audio_file_deleted = 0`）：`+10 分`
- **歌名完全精确一致**：`+10 分`（高于净化后模糊匹配的 `+5 分`）
- **高音质无损格式优先**：`FLAC / ALAC / WAV`（`+3 分`）优先于 `MP3 / AAC`（`+1 分`）

### 4. 歌单导入全流程闭环
- **解析预览即刻查重**：粘贴歌单链接或从云端账号导入时，毫秒级完成全列表比对并在前端呈现收录徽章与已收录路径；
- **任务下载极速复用**：下载任务执行时，优先复用已识别的本地音频路径，跳过重复抓取直接纳入生成的 `.m3u8` 歌单，极大节省网络带宽与磁盘写入。

---

## ⚠️ 风险说明与第三方集成免责说明 (Risk Disclosure & Disclaimer)

在使用本项目前，请您充分知悉并理解以下集成机制与潜在风险：

### 1. 飞牛官方底层数据库直连机制与潜在风险
- **集成原理**：为实现歌单秒级无感同步、全库毫秒级查重去重与物理删除联动，TRIM Music Hub 直连并读写飞牛 NAS 官方「飞牛音乐 (`trim.music`)」底座 SQLite 数据库（`/usr/local/apps/@appdata/trim.music/db/music.db`）。
- **潜在风险**：飞牛官方目前未对外提供公开的数据库写操作标准 API。当飞牛系统或飞牛音乐 App 发布大版本 OTA 升级时，官方可能对数据库表结构（字段增删、重命名或外键约束）进行调整，直接写操作可能因架构差异遇到兼容性挑战。

### 2. 本项目的四重防损与高弹性容灾体系 (OTA Resilience)
为最大程度保障用户数据与曲库资产安全，本项目内置了工业级的容灾与自适应机制：
- **动态表结构自省 (Dynamic Reflection)**：严禁硬编码静态 SQL 列名。程序每次写入前均动态调用 SQLite 原生 `PRAGMA table_info`，自动剔除官方已删除的字段，并为官方新增的非空列补齐安全初值，平滑抵抗字段变动；
- **版本指纹与安全模式 (Safe Mode Fallback)**：每次同步前自动计算核心表 DDL 的 SHA-256 指纹。若探测到底层发生断代式结构变更，系统将**自动熔断对官方数据库的直接写入**并切换至安全模式，杜绝向未知数据库写入脏数据；
- **短事务原子回滚 (Rollback & Busy Timeout)**：设置 30 秒高弹性退避等待超时（`busy_timeout = 30000`），礼貌避让飞牛官方后台的并发扫描；所有操作均置于严格的原子事务保护中，任何单步失败均立即触发全局 `ROLLBACK`；
- **工业标准双轨文件保底 (Dual-Track Resilience)**：歌曲下载与歌单创建时，标准音频 ID3/Vorbis 标签、内嵌高清封面、同级伴随 `.lrc` 歌词与工业标准 `.m3u8` 播放列表均先行在硬盘持久化。即便数据库彻底重构，飞牛官方自带的文件监听扫描器也能通过标准文件完整重构曲库。

### 3. 数据安全与运维建议
- **跨版本固件升级**：建议在进行飞牛 NAS 重大跨版本固件升级前，做好数据备份；
- **物理删除二次确认**：在「曲库管理」或「歌单管理」中勾选“同时物理删除磁盘文件”属于不可逆的物理覆写操作，请务必仔细复核确认弹窗。

### 4. 技术中立与版权免责声明
- 本项目属于技术中立的本地多媒体管理工具，核心功能为本地音乐元数据刮削、曲库去重、歌单整理与格式转码；
- 在线检索与下载依赖用户配置的音源扩展脚本或接口，软件本身不内置任何未授权受版权保护的音源文件；请所有使用者遵守当地版权法律法规，仅用于个人备份与技术学习，严禁用于任何商业牟利行为。

---

## 📋 常见问题与排错 (FAQ)

#### Q1: 搜歌提示“未收录”，点击下载后下载的文件在哪里？
A: 下载的文件会自动归档至您挂载的音乐根目录 `/media/music/<歌手名>/<歌手名> - <歌名>/`，格式为标准的 `.flac` 无损音频并附带同名 `.lrc` 歌词文件。飞牛音乐 App 会自动触发媒体扫描入库。

#### Q2: 为什么提示“无法打开数据库文件”？
A: 飞牛官方音乐数据库 `/usr/local/apps/@appdata/trim.music/db/music.db` 需要读写权限，请确认已按照指引挂载了 `/usr/local/apps/@appdata/trim.music/db` 卷，且容器具备读写权限（默认已配置为 `:rw`）。

#### Q3: 文件下载后的所有者权限问题？
A: 容器默认使用环境变量 `PUID=1000` 与 `PGID=1000` 对归档的音频和歌单自动赋权 `777`，与飞牛首个管理员账号完美兼容，不会出现 NAS 文件管理器无权限修改的问题。

---

## 📄 开源许可证
本项目遵循 [MIT License](LICENSE) 开源。
