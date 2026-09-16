# TRIM Music Hub 前端开发规范与 UI 组件约定 (UI_GUIDELINES.md)

> **⚠️ 强制规范（所有协作 AI 与开发者必须严格遵守）**：
> 本项目前端已全面确立 **`shadcn-vue`** (基于 `Radix Vue` + `Tailwind CSS`) 为唯一指定的 UI 组件标准。
> **页面中所有控件（按钮、输入框、徽章、气泡确认等）必须全部使用组件库中的原子组件。二次确认操作一律严禁使用居中 Modal 弹框，必须使用就近锚定的 Popup 气泡确认框（`Popconfirm`）。**

---

## 一、 技术栈与架构基准

1. **核心框架**：`Vue 3` (Composition API + `<script setup>`) + `TypeScript`
2. **样式系统**：`Tailwind CSS` + 深色拟态系统变量
3. **UI 原语标准**：**`shadcn-vue` / `Radix Vue`**（底层无障碍、键盘交互与焦点管理）
4. **工具库**：`clsx` + `tailwind-merge`（统一通过 `@/lib/utils` 中的 `cn()` 处理类名合并）
5. **图标系统**：`lucide-vue-next`（保持图标线宽与视觉语调一致）

---

## 二、 控件与组件使用规范

### 1. 原子组件清单 (`src/components/ui/`)
所有原子级控件必须从此目录引入：
- **按钮**：`@/components/ui/button` (`Button`, 支持 `brand`, `default`, `destructive`, `destructiveOutline`, `outline`, `ghost` 变体及 `sm`, `default`, `lg`, `icon`, `iconSm` 尺寸)
- **输入框**：`@/components/ui/input` (`Input`, 内置深色玻璃拟态背景与焦点 Emerald 呼吸环)
- **徽章**：`@/components/ui/badge` (`Badge`, 支持 `brand`, `success`, `destructive`, `indigo`, `amber`, `default`, `outline`)
- **气泡确认框**：`@/components/ui/popconfirm` (`Popconfirm`, 基于 Radix Vue Popover 原语)
- **复选框**：`@/components/ui/checkbox` (`Checkbox`)
- **浮动层原语**：`@/components/ui/popover` (`Popover`, `PopoverTrigger`, `PopoverContent`)

### 2. ⚡ 二次确认交互强制铁律 (Popup over Modal)
- ❌ **严禁调用原生 `confirm()` / `alert()` / `prompt()`**。
- ❌ **严禁使用全屏居中 Modal/Dialog 进行二次确认**（删除单曲、删除歌单、清空历史、中止任务等）。
- ✅ **二次确认必须使用 `Popconfirm`（Popup 气泡确认）**：
  - 理由：居中 Modal 会产生割裂的全屏暗化遮罩，打断用户当前视线和上下文；而 Popup 气泡确认就近吸附在操作按钮旁，视觉轻巧直观，点击遮罩或按 ESC 即可瞬时取消。
  - 使用示例：
    ```vue
    <Popconfirm
      title="确定要彻底删除？"
      description="将物理删除该音频文件，无法撤销。"
      confirmText="彻底删除"
      :danger="true"
      @confirm="handleDelete"
    >
      <Button variant="ghost" size="icon">
        <Trash2 class="w-4 h-4" />
      </Button>
    </Popconfirm>
    ```

---

## 三、 视觉与设计语言规范

1. **主色调**：
   - 品牌绿（Brand Emerald）：`#10b981` (`brand-500`) 与 `#059669` (`brand-600`)；
   - 底色：深邃黑曜灰 `bg-slate-950`；
   - 卡片背景：`bg-slate-900/80` 配以 `border-slate-800/80` 与 `backdrop-blur-xl`；
2. **文本阶梯**：
   - 主标题：`text-white font-bold`；
   - 次要说明：`text-slate-400 text-xs`；
   - 代码/路径/指标：`font-mono text-slate-300`；
3. **响应式与 PC 桌面端兼容**：
   - 所有组件开发必须同时考虑 **PC 桌面端鼠标光标**与 **手机移动端触摸**。
   - 按钮和可点击项必须包含 `hover:`, `active:`, `disabled:` 明确的微交互动效。
