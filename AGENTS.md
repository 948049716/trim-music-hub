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

### 2. 开发与构建规范 (Development & HMR)
- **日常修改严禁手动执行 `npm run build`**！
- 前端常驻启动 Vite 开发服务器（Port `5175`），支持全量 WebSocket HMR 热更新。公网反代域名 `https://music.miong.me:9481` 已直通开发服务器。
- 修改 `frontend/src/` 代码保存即可毫秒级热生效，只有在用户明确下达“打包构建”或“发布测试”指令时才执行构建。

### 3. 数据与隐私保护规范 (Anti-Leak)
- 本地任务历史与凭证存放在 `data/` 目录下（如 `data/history.json`），已由 `.gitignore` 与 `.dockerignore` 排除。
- 严禁在修改代码时将 `data/` 下的用户个人曲目路径、历史记录、账号凭据硬编码写入源码或提交到公共分支。

### 4. 架构分层规范
- **前端 SPA**：位于 `frontend/`，纯单页面应用。
- **后端胶水层**：位于 `server.mjs`，纯标准库 Node.js 服务（4175）。
- **底层驱动脚本**：位于 `db_ops.py` 与 `scripts/`，直通飞牛 SQLite 数据库与音源下载。
- **公共技能分离**：智能体技能存放在 `/vol1/1000/Project/skills/`，严禁在当前业务工程内混合散落独立技能。

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

