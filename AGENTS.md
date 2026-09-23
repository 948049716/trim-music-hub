# AGENTS.md - Agent Work Guidelines for TRIM Music Hub

> 本文件专为后续接手的 AI 智能体（如 OpenClaw、Cursor、Claude Code 等）设定项目开发约束。任何进入该项目的 AI 必须首先阅读并强制遵守以下规约。

---

## 🚨 强制规则 (Rules for AI Agents)

### 1. 前端 UI 组件库强制约定 (全量统一组件库)
- **唯一指定组件库**：**`shadcn-vue`** (底层为 `radix-vue` + `tailwind-merge` + `clsx`)。
- **配置与基准文件**：`frontend/components.json` 与 `frontend/UI_GUIDELINES.md`。
- **控件使用要求 (必须全部使用组件库原子控件)**：
  - 页面中所有的按钮必须使用 `@/components/ui/button` (`Button`)；
  - 所有的文本框必须使用 `@/components/ui/input` (`Input`)；
  - 所有的状态徽章必须使用 `@/components/ui/badge` (`Badge`)；
  - 所有的多选复选框必须使用 `@/components/ui/checkbox` (`Checkbox`)；
  - 严禁手写零散、不带设计变量的原生 HTML 标签。
- **二次确认交互铁律 (禁止使用 Modal，必须使用 Popup 气泡确认)**：
  - ❌ **严禁使用原生弹框**：禁止调用 `confirm()`、`alert()`、`prompt()`；
  - ❌ **严禁对二次确认操作使用居中大 Modal/Dialog 弹窗**（大面积居中遮罩会严重阻断用户操作流，属于笨重设计）；
  - ✅ **二次确认必须使用 Popup / 气泡确认框**（统一使用 `@/components/ui/popconfirm` 的 `Popconfirm` 组件，基于 Radix Vue Popover 原语实现，就近锚定在触发按钮旁弹出确认，轻量优雅且支持键盘快捷关闭）。
- **严禁私自引入其他重型侵入式框架**：
  - 严禁安装 Element Plus、Ant Design Vue、Vuetify、Arco Design 等第三方打包库。

### 2. 开发与生产独立并行规范 (三层隔离架构 - 强制铁律)
- **核心原则**：开发环境与生产环境完全独立并行，互不干扰、互不影响。
- **端口与网络隔离**：
  - **正式生产环境**：Docker 容器 `trim-music-hub`，占用端口 `4175`，Nginx 反代域名 `https://music.miong.me:9481` 与 `https://music-api.miong.me:9481`。
  - **独立开发环境**：
    - 前端开发服务器（Vite HMR）：端口 `5175`，支持毫秒级热更新。
    - 后端开发服务（Node.js `--watch`）：端口 `3175`，自动热重启。
    - 开发入口：局域网 `http://192.168.0.2:5175` 或外网反代 `https://musicdev.miong.me:9481`。
- **数据与持久化隔离**：
  - **生产数据目录**：`/vol1/1000/docker/trim-music-hub/data/`（正式任务队列、生产账号凭据与生产设置）。
  - **开发数据目录**：`/vol1/1000/Project/trim-music-hub/data/`（独立本地测试缓存，由 `.env` 中的 `DATA_DIR` 控制，严禁污染生产数据）。
- **开发与部署铁律**：
  - **平时改代码、调试 Bug、加功能，一律仅在开发环境（3175/5175）下进行**，严禁私自修改、重启或覆盖正式 Docker 容器；
  - **日常修改严禁手动执行 `npm run build`**，修改 `frontend/src/` 或 `server.mjs` 自动依靠 Vite HMR / Node `--watch` 毫秒级热更新；
  - **环境管理命令**：
    - 启动开发环境：`bash start_dev.sh`
    - 停止开发环境：`bash stop_dev.sh`
  - **仅在用户明确下达“发布上线”、“部署到正式环境”指令时**，才允许执行 `bash deploy_prod.sh` 进行生产镜像构建与容器平滑滚动更新。

### 3. 数据与隐私保护规范 (Anti-Leak)
- 本地任务历史与凭证存放在 `data/` 目录下（如 `data/history.json`），已由 `.gitignore` 与 `.dockerignore` 排除。
- 严禁在修改代码时将 `data/` 下的用户个人曲目路径、历史记录、账号凭据硬编码写入源码或提交到公共分支。

### 4. 架构分层规范
- **前端 SPA**：位于 `frontend/`，纯单页面应用。
- **后端胶水层**：位于 `server.mjs`，纯标准库 Node.js 服务（4175）。
- **底层驱动脚本**：位于 `db_ops.py` 与 `scripts/`，直通飞牛 SQLite 数据库与音源下载。
- **公共技能分离**：智能体技能存放在 `/vol1/1000/Project/skills/`，严禁在当前业务工程内混合散落独立技能。
- **后端接口文档**：所有对外暴露的 RESTful 与 SSE 接口规范必须统一维护在项目根目录的 `API_DOCUMENTATION.md` 中。今后只要在 `server.mjs` 中新增、修改或弃用任何 API，必须同步更新该文档。
- **飞牛数据库规范与跨机开发准则 (Database Guidelines)**：
  - 飞牛官方底座数据库 `music.db` 的完整表结构（含字段注释与索引）统一收录在 `docs/fnos_music_schema.sql`，实体关系与跨机离线开发手册见 `docs/DATABASE_SCHEMA.md`。
  - 在异地或无 NAS 数据库权限的开发机上增加后端功能时，禁止盲猜表结构；使用 `sqlite3 ./data/mock_music.db < docs/fnos_music_schema.sql` 初始化本地测试库，并通过 `FNOS_DB_PATH=./data/mock_music.db` 启动后端。
  - 对 `track`、`playlist`、`audio_file` 等核心表执行增删改查时，必须严格遵守原库的 `guid` 全局唯一、删除标记（`is_audio_file_deleted` / `is_admin_deleted`）以及多对多关联约束（如 `track_artist`、`playlist_track`）。

### 5. UI/UX 设计与重构规范 (强制使用 ui-ux-pro-max 技能)
- **强制设计技能**：今后凡是涉及到任何前端页面重构、页面设计、新功能组件开发或交互体验优化，**必须强制默认调用 `ui-ux-pro-max` 技能**作为设计与审查指导。
- **移动端原生级体验铁律**：
  - **禁止页面缩放**：保持移动 Web App 级锁定，禁止非受控变焦；移动端输入框字号保底 16px 防止 iOS 自动放大。
  - **输入框禁止自动聚焦**：打开模态框、抽屉、气泡或切换 Tab 时，一律拦截自动 focus，严禁软键盘未受邀请突然弹起遮挡界面。
  - **滚动条统一封装**：全局和局部滚动条必须统一使用现代极简微细轨磨砂设计（`.custom-scrollbar` / `.workbench-list-scroll`），杜绝粗笨原生滚动条。
  - **二次确认统一规范**：必须使用 `@/components/ui/popconfirm` 磨砂微光气泡弹窗，严禁居中大遮罩 Modal，严禁原生 alert/confirm。
  - **物理惯性弹簧切换铁律 (全量 Tab/Segment 必须使用 SpringTabs/useSpringInertia)**:
    - ❌ **严禁使用瞬变或线性硬切换**：任何类似 Tab、Segment、Sub-tab、分类过滤药丸等切换交互，严禁仅通过静态 CSS active 类或生硬的瞬变完成；
    - ✅ **强制使用物理欠阻尼谐振子弹簧模型 (Underdamped Harmonic Oscillator + Viscoelastic Rebound)**：
      - 必须使用封装好的 `@/components/ui/tabs` 的 `<SpringTabs>` 组件或 `@/composables/useSpringInertia` 组合式函数；
      - 动效规律：跨越步长（距离）越远，初始冲量和恢复力越大；滑块具有随速度变化的惯性拉伸与压缩（Squash & Stretch），越过目标点产生过冲（Overshoot），随后切换高粘滞阻尼进行慢回弹（Viscoelastic Slow Rebound）平滑归位；
      - 硬件加速：采用 `transform: translate3d(...) scaleX(...)`，禁用侵入性全屏重绘，保持纯平磨砂或品牌主色微光胶囊底座。

### 6. 界面文案与需求隔离铁律 (Strict Rule - 强制规则)
- ❌ **严禁把用户对话中的需求类/解释类/提示类内容搬到界面上**：
  - 除非用户明确、特意要求在界面上展示某段文案，否则任何对话中的需求背景、权限解释、实现逻辑、管理员特权提示、安全隐私冗余声明等，**一律严禁作为 UI 提示文字或描述出现在前端界面中**；
  - 界面所有标签、标题、按钮、占位符必须保持精炼、专业、产品化与原生质感，绝不出现任何开发需求痕迹或多余的说教式说明。

