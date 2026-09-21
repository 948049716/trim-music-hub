<script setup lang="ts">
import { ref, computed } from 'vue';
import type { TaskState, QueueTask, CurrentUser } from '../../types';
import { api } from '@/api';
import { showToast } from '@/composables/useToast';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Popconfirm } from '@/components/ui/popconfirm';
import { Card } from '@/components/ui/card';
import {
  Plus,
  Square,
  RefreshCw,
  Terminal,
  GripVertical,
  Trash2,
  Music2,
  ListMusic,
  CheckCircle2,
  Clock3,
  AlertCircle,
  StopCircle,
  Layers,
  ChevronRight,
  User,
  Filter,
  Sparkles,
  Copy,
} from 'lucide-vue-next';

const props = defineProps<{
  task: TaskState;
  logs: string[];
  queue?: QueueTask[];
  currentUser?: CurrentUser | null;
}>();

const emit = defineEmits<{
  (e: 'open-task-modal'): void;
  (e: 'stop-task'): void;
  (e: 'refresh-queue'): void;
}>();

// Filter & View State
type QueueFilter = 'all' | 'active' | 'completed';
const filter = ref<QueueFilter>('all');
const showLogs = ref(false);
const autoScrollLogs = ref(true);
const logContainerRef = ref<HTMLElement | null>(null);

// Drag & Drop State
const draggedTaskId = ref<string | null>(null);
const dragOverTaskId = ref<string | null>(null);

const activeQueue = computed(() => {
  const list = props.queue || [];
  return [...list].sort((a, b) => {
    // Running first, then pending sorted by order, then others by created_at desc
    if (a.status === 'running') return -1;
    if (b.status === 'running') return 1;
    if (a.status === 'pending' && b.status === 'pending') {
      return (a.order ?? 0) - (b.order ?? 0);
    }
    if (a.status === 'pending') return -1;
    if (b.status === 'pending') return 1;
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  });
});

const filteredQueue = computed(() => {
  if (filter.value === 'active') {
    return activeQueue.value.filter(t => t.status === 'pending' || t.status === 'running');
  }
  if (filter.value === 'completed') {
    return activeQueue.value.filter(t => ['success', 'failed', 'stopped'].includes(t.status));
  }
  return activeQueue.value;
});

const counts = computed(() => {
  const list = props.queue || [];
  return {
    total: list.length,
    running: list.filter(t => t.status === 'running').length,
    pending: list.filter(t => t.status === 'pending').length,
    completed: list.filter(t => ['success', 'failed', 'stopped'].includes(t.status)).length,
  };
});

const isRunning = computed(() => ['downloading', 'parsing', 'finalizing'].includes(props.task.status));

const runningTaskDetails = computed(() => {
  if (!isRunning.value) return null;
  const processed = (props.task.reused_count || 0) + (props.task.downloaded_count || 0) + (props.task.failed_count || 0);
  const total = props.task.total || 0;
  const percent = total > 0 ? Math.min(100, Math.round((processed / total) * 100)) : 0;
  return {
    title: props.task.playlist_name || '任务进行中',
    step: props.task.current_track?.step || (props.task.current_track ? `正在处理: ${props.task.current_track.artist} - ${props.task.current_track.title}` : '正在同步...'),
    cover: props.task.current_track?.cover || '',
    processed,
    total,
    percent,
    reused: props.task.reused_count || 0,
    downloaded: props.task.downloaded_count || 0,
    failed: props.task.failed_count || 0,
    speed: props.task.speed || '',
    user: props.task.user,
    target: props.task.target,
  };
});

function getTaskProcessed(task: QueueTask) {
  if ((task.status === 'running' || task.status === 'downloading') && isRunning.value) {
    const currentRunProcessed = (props.task.downloaded_count || 0) + (props.task.reused_count || 0) + (props.task.failed_count || 0);
    if (currentRunProcessed > 0) return currentRunProcessed;
  }
  if (task.processed_count !== undefined && task.processed_count !== null && task.processed_count > 0) {
    return task.processed_count;
  }
  return (task.downloaded_count || 0) + (task.reused_count || 0) + (task.failed_count || 0);
}

// Drag & drop handlers for pending tasks
function handleDragStart(task: QueueTask, event: DragEvent) {
  if (task.status !== 'pending') {
    event.preventDefault();
    return;
  }
  draggedTaskId.value = task.id;
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', task.id);
  }
}

function handleDragOver(task: QueueTask, event: DragEvent) {
  if (task.status !== 'pending' || !draggedTaskId.value || draggedTaskId.value === task.id) return;
  event.preventDefault();
  dragOverTaskId.value = task.id;
}

function handleDragLeave(task: QueueTask) {
  if (dragOverTaskId.value === task.id) {
    dragOverTaskId.value = null;
  }
}

async function handleDrop(targetTask: QueueTask, event: DragEvent) {
  event.preventDefault();
  dragOverTaskId.value = null;
  const sourceId = draggedTaskId.value;
  draggedTaskId.value = null;

  if (!sourceId || sourceId === targetTask.id || targetTask.status !== 'pending') return;

  const pendingList = activeQueue.value.filter(t => t.status === 'pending');
  const sourceIndex = pendingList.findIndex(t => t.id === sourceId);
  const targetIndex = pendingList.findIndex(t => t.id === targetTask.id);

  if (sourceIndex === -1 || targetIndex === -1) return;

  const reordered = [...pendingList];
  const [removed] = reordered.splice(sourceIndex, 1);
  reordered.splice(targetIndex, 0, removed);

  try {
    const res = await api.reorderTasks(reordered.map(t => t.id));
    if (res.ok) {
      showToast('任务队列顺序已更新', 'success');
      emit('refresh-queue');
    } else {
      showToast(res.error || '调整顺序失败', 'error');
    }
  } catch (e: any) {
    showToast(e.message || '网络异常', 'error');
  }
}

function handleDragEnd() {
  draggedTaskId.value = null;
  dragOverTaskId.value = null;
}

// Cancel or remove task
async function copyTaskUrl(url?: string) {
  if (!url) return;
  try {
    await navigator.clipboard.writeText(url);
    showToast('歌单链接已复制到剪贴板', 'success');
  } catch {
    const el = document.createElement('textarea');
    el.value = url;
    document.body.appendChild(el);
    el.select();
    document.execCommand('copy');
    document.body.removeChild(el);
    showToast('歌单链接已复制到剪贴板', 'success');
  }
}

async function handleCancelTask(task: QueueTask) {
  try {
    const res = await api.cancelTask(task.id);
    if (res.ok) {
      showToast(res.message || (task.status === 'running' ? '已终止并移除运行中的任务' : (task.status === 'pending' ? '排队任务已取消' : '任务记录已删除')), 'success');
      emit('refresh-queue');
    } else {
      showToast(res.error || '操作失败', 'error');
    }
  } catch (e: any) {
    showToast(e.message || '网络异常', 'error');
  }
}

// Clear completed tasks
async function handleClearCompleted() {
  try {
    const res = await api.clearCompletedTasks();
    if (res.ok) {
      showToast('已清理所有已完成任务', 'success');
      emit('refresh-queue');
    } else {
      showToast(res.error || '清理失败', 'error');
    }
  } catch (e: any) {
    showToast(e.message || '网络异常', 'error');
  }
}

function getTaskBadge(status: string) {
  switch (status) {
    case 'running': return { text: '正在执行', variant: 'brand' as const, icon: RefreshCw, spin: true };
    case 'downloading': return { text: '下载中', variant: 'brand' as const, icon: RefreshCw, spin: true };
    case 'parsing': return { text: '解析中', variant: 'warning' as const, icon: RefreshCw, spin: true };
    case 'finalizing': return { text: '入库中', variant: 'brand' as const, icon: RefreshCw, spin: true };
    case 'pending': return { text: '排队等待', variant: 'warning' as const, icon: Clock3, spin: false };
    case 'success': return { text: '已完成', variant: 'success' as const, icon: CheckCircle2, spin: false };
    case 'failed': return { text: '失败', variant: 'destructive' as const, icon: AlertCircle, spin: false };
    case 'stopped': return { text: '已中止', variant: 'outline' as const, icon: StopCircle, spin: false };
    default: return { text: status === 'idle' ? '待命' : status, variant: 'outline' as const, icon: Clock3, spin: false };
  }
}

function formatTaskTime(isoString?: string) {
  if (!isoString) return '--:--';
  const d = new Date(isoString);
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}
</script>

<template>
  <div class="h-full min-h-0 flex-1 flex flex-col space-y-4 overflow-y-auto custom-scrollbar pb-36 sm:pb-12 pr-0.5" style="-webkit-overflow-scrolling: touch; scroll-behavior: smooth;">
    <!-- 顶部状态栏与操作工具条 -->
    <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between shrink-0">
      <!-- 队列统计胶囊与筛选切换 -->
      <div class="flex items-center gap-1.5 p-1 rounded-xl bg-muted/60 border border-border/70 self-start max-w-full overflow-x-auto no-scrollbar shrink-0">
        <button
          type="button"
          class="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-1.5"
          :class="filter === 'all' ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'"
          @click="filter = 'all'"
        >
          <span>全部</span>
          <span class="px-1.5 py-0.2 rounded-full text-[10px] font-mono bg-muted text-muted-foreground">{{ counts.total }}</span>
        </button>
        <button
          type="button"
          class="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-1.5"
          :class="filter === 'active' ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'"
          @click="filter = 'active'"
        >
          <span>执行与等待</span>
          <span
            v-if="counts.running + counts.pending > 0"
            class="px-1.5 py-0.2 rounded-full text-[10px] font-mono bg-primary/20 text-primary font-bold animate-pulse"
          >
            {{ counts.running + counts.pending }}
          </span>
          <span v-else class="px-1.5 py-0.2 rounded-full text-[10px] font-mono bg-muted text-muted-foreground">0</span>
        </button>
        <button
          type="button"
          class="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-1.5"
          :class="filter === 'completed' ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'"
          @click="filter = 'completed'"
        >
          <span>已完成</span>
          <span class="px-1.5 py-0.2 rounded-full text-[10px] font-mono bg-muted text-muted-foreground">{{ counts.completed }}</span>
        </button>
      </div>

      <!-- 右侧操作按钮组 -->
      <div class="flex items-center gap-2 self-end sm:self-auto">
        <Popconfirm
          v-if="counts.completed > 0"
          title="清理已完成任务？"
          description="将从队列列表中移除已成功或已结束的历史记录。"
          confirmText="清理完成项"
          :danger="false"
          side="bottom"
          align="end"
          @confirm="handleClearCompleted"
        >
          <Button variant="outline" size="sm" class="h-8 px-2.5 text-xs text-muted-foreground hover:text-foreground gap-1.5">
            <Trash2 class="h-3.5 w-3.5" />清空已完成
          </Button>
        </Popconfirm>

        <Button
          variant="outline"
          size="sm"
          class="h-8 px-2.5 text-xs gap-1.5"
          :class="{ 'bg-muted text-primary': showLogs }"
          @click="showLogs = !showLogs"
        >
          <Terminal class="h-3.5 w-3.5" />
          <span>{{ showLogs ? '收起日志' : '实时日志' }}</span>
          <span v-if="logs.length" class="text-[10px] text-muted-foreground font-mono">({{ logs.length }})</span>
        </Button>

        <Button
          variant="brand"
          size="sm"
          class="h-8 px-3 text-xs font-semibold gap-1.5 shadow-sm active:scale-95"
          @click="emit('open-task-modal')"
        >
          <Plus class="h-3.5 w-3.5" />新建任务
        </Button>
      </div>
    </div>

    <!-- 紧凑型正在执行状态栏 (仅在有正在运行的任务时展示，告别臃肿大唱片) -->
    <div
      v-if="runningTaskDetails"
      class="relative overflow-hidden rounded-xl border border-primary/35 bg-card/90 p-3.5 sm:p-4 shadow-sm backdrop-blur-sm"
    >
      <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div class="flex items-center gap-3 min-w-0">
          <div class="relative h-10 w-10 sm:h-11 sm:w-11 shrink-0 rounded-lg overflow-hidden border border-primary/40 bg-muted grid place-items-center">
            <img
              v-if="runningTaskDetails.cover"
              :src="runningTaskDetails.cover"
              class="h-full w-full object-cover select-none pointer-events-none"
              alt="封面"
            />
            <RefreshCw v-else class="h-5 w-5 text-primary animate-spin" />
          </div>

          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2 flex-wrap">
              <Badge variant="brand" class="text-[10px] py-0 px-1.5 h-4.5 gap-1">
                <span class="inline-block h-1.5 w-1.5 rounded-full bg-primary animate-pulse" />
                {{ props.task.status === 'downloading' ? '下载中' : (props.task.status === 'parsing' ? '解析中' : (props.task.status === 'finalizing' ? '入库中' : '正在执行')) }}
              </Badge>
              <span class="text-xs sm:text-sm font-bold text-foreground truncate max-w-[200px] sm:max-w-md">{{ runningTaskDetails.title }}</span>
              <span v-if="runningTaskDetails.speed" class="text-[10px] font-mono font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-full shrink-0 flex items-center gap-1">
                ⚡ {{ runningTaskDetails.speed }}
              </span>
            </div>
            <p class="mt-1 text-[11px] text-muted-foreground truncate font-mono flex items-center gap-1.5">
              <span class="truncate">{{ runningTaskDetails.step }}</span>
            </p>
          </div>
        </div>

        <div class="flex items-center gap-3 shrink-0 self-end sm:self-auto">
          <!-- 紧凑指标 -->
          <div class="text-right text-[11px] font-mono hidden md:block">
            <span v-if="runningTaskDetails.speed" class="text-primary font-bold mr-2.5">⚡ {{ runningTaskDetails.speed }}</span>
            <span class="text-success font-semibold">入库 {{ runningTaskDetails.downloaded }}</span>
            <span class="text-muted-foreground mx-1">·</span>
            <span class="text-info font-semibold">复用 {{ runningTaskDetails.reused }}</span>
            <span v-if="runningTaskDetails.failed > 0" class="text-destructive font-semibold ml-1">· 失败 {{ runningTaskDetails.failed }}</span>
          </div>

          <!-- 停止当前任务按钮 -->
          <Popconfirm
            title="终止当前运行任务？"
            description="已入库的音乐文件将保留，当前正在进行的下载将被中止。"
            confirmText="终止任务"
            :danger="true"
            side="bottom"
            align="end"
            @confirm="emit('stop-task')"
          >
            <Button variant="destructiveOutline" size="sm" class="h-7 px-2.5 text-xs gap-1">
              <Square class="h-3 w-3 fill-current" />终止
            </Button>
          </Popconfirm>
        </div>
      </div>

      <!-- 细致进度条 -->
      <div class="mt-3 flex items-center gap-3">
        <Progress :model-value="runningTaskDetails.percent" class="h-1.5 bg-muted flex-1" />
        <span v-if="runningTaskDetails.speed" class="text-xs font-bold font-mono text-primary shrink-0 sm:hidden">
          ⚡ {{ runningTaskDetails.speed }}
        </span>
        <span class="text-xs font-bold tabular-nums text-primary font-mono shrink-0">
          {{ runningTaskDetails.percent }}% ({{ runningTaskDetails.processed }}/{{ runningTaskDetails.total }})
        </span>
      </div>
    </div>

    <!-- 任务队列列表与调度器 -->
    <Card class="overflow-hidden p-0 border-border/80 shadow-sm">
      <div class="px-4 py-3 border-b border-border/70 flex items-center justify-between bg-[hsl(var(--surface-inset)/.45)]">
        <div class="flex items-center gap-2">
          <Layers class="h-4 w-4 text-primary" />
          <h3 class="text-xs sm:text-sm font-bold text-foreground">任务队列</h3>
          <span class="text-[10px] text-muted-foreground">按住手柄拖拽可调整排队顺序</span>
        </div>
        <div class="flex items-center gap-2 text-[11px] text-muted-foreground font-mono">
          <span>共 {{ filteredQueue.length }} 项</span>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-if="filteredQueue.length === 0" class="py-14 text-center px-4">
        <div class="inline-grid h-12 w-12 place-items-center rounded-2xl bg-muted/60 text-muted-foreground mb-3">
          <Layers class="h-6 w-6 opacity-60" />
        </div>
        <p class="text-xs sm:text-sm font-semibold text-foreground">当前没有待处理或运行的任务</p>
        <p class="mt-1 text-[11px] text-muted-foreground max-w-xs mx-auto">
          点击右上角「新建任务」导入歌单，或在全网搜索中点击下载单曲。
        </p>
        <Button variant="brand" size="sm" class="mt-4 h-8 text-xs gap-1.5" @click="emit('open-task-modal')">
          <Plus class="h-3.5 w-3.5" />新建任务
        </Button>
      </div>

      <!-- 任务列表 -->
      <div v-else class="divide-y divide-border/60">
        <div
          v-for="task in filteredQueue"
          :key="task.id"
          class="group relative flex items-center gap-2.5 sm:gap-3.5 p-2.5 sm:p-3 transition-colors select-none"
          :class="[
            task.status === 'running' ? 'bg-primary/5' : 'hover:bg-muted/40',
            dragOverTaskId === task.id ? 'border-t-2 border-primary bg-primary/10' : '',
            draggedTaskId === task.id ? 'opacity-40' : ''
          ]"
          :draggable="task.status === 'pending'"
          @dragstart="handleDragStart(task, $event)"
          @dragover="handleDragOver(task, $event)"
          @dragleave="handleDragLeave(task)"
          @drop="handleDrop(task, $event)"
          @dragend="handleDragEnd"
        >
          <!-- 拖拽手柄与序号 -->
          <div class="flex items-center gap-1 shrink-0">
            <div
              v-if="task.status === 'pending'"
              class="cursor-grab active:cursor-grabbing p-1 text-muted-foreground/50 hover:text-foreground transition-colors rounded"
              title="拖拽调整执行顺序"
            >
              <GripVertical class="h-4 w-4" />
            </div>
            <div v-else class="w-6 grid place-items-center text-muted-foreground/35">
              <span class="inline-block h-1.5 w-1.5 rounded-full bg-border" />
            </div>
            <span class="text-[10px] font-mono text-muted-foreground w-4 text-center">
              {{ task.order ? `#${task.order}` : '-' }}
            </span>
          </div>

          <!-- 封面或图标 -->
          <div class="relative h-9 w-9 sm:h-10 sm:w-10 shrink-0 rounded-lg overflow-hidden border border-border/80 bg-muted grid place-items-center">
            <img
              v-if="task.cover"
              :src="task.cover"
              class="h-full w-full object-cover select-none pointer-events-none"
              alt="封面"
            />
            <component
              :is="task.type === 'single' ? Music2 : ListMusic"
              v-else
              class="h-4 w-4 text-muted-foreground"
            />
          </div>

          <!-- 任务标题与属性 -->
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-1.5 sm:gap-2 flex-wrap">
              <h4 class="truncate text-xs sm:text-sm font-semibold text-foreground max-w-[280px] sm:max-w-md">
                {{ task.title }}
              </h4>
              <Badge variant="outline" class="text-[9px] py-0 px-1.5 h-4">
                {{ task.type === 'single' ? '单曲' : '歌单' }}
              </Badge>
              <Badge v-if="task.quality" variant="secondary" class="text-[9px] py-0 px-1.5 h-4 font-mono uppercase">
                {{ task.quality }}
              </Badge>
              <!-- 管理员全员归属标签 -->
              <Badge
                v-if="currentUser?.isAdmin && task.owner_user"
                variant="outline"
                class="text-[9px] py-0 px-1.5 h-4 font-mono text-muted-foreground border-dashed gap-0.5"
              >
                <User class="h-2.5 w-2.5" />{{ task.owner_user }}
              </Badge>
            </div>

            <!-- 次要信息 -->
            <div class="mt-1 flex items-center gap-x-3 gap-y-1 text-[10px] text-muted-foreground font-mono flex-wrap">
              <span>{{ formatTaskTime(task.created_at) }}</span>
              <span v-if="task.target">
                {{ task.target === 'public' ? '公共曲库' : `专属 (${task.user})` }}
              </span>
              <span v-if="task.total > 0">
                进度: {{ getTaskProcessed(task) }}/{{ task.total }}
              </span>
              <span v-if="(task.status === 'running' || task.status === 'downloading') && (task.speed || props.task.speed)" class="text-primary font-bold">
                ⚡ {{ task.speed || props.task.speed }}
              </span>
              <span v-if="task.error" class="text-destructive truncate max-w-[200px]">
                {{ task.error }}
              </span>
            </div>
          </div>

          <!-- 状态徽章 -->
          <div class="shrink-0">
            <Badge
              :variant="getTaskBadge(task.status).variant"
              class="text-[10px] py-0.5 px-2 font-medium gap-1"
            >
              <component
                :is="getTaskBadge(task.status).icon"
                class="h-3 w-3"
                :class="{ 'animate-spin': getTaskBadge(task.status).spin }"
              />
              <span>{{ getTaskBadge(task.status).text }}</span>
            </Badge>
          </div>

          <!-- 复制链接与取消/移除操作 -->
          <div class="flex items-center gap-1 shrink-0">
            <Button
              v-if="task.url"
              variant="ghost"
              size="sm"
              class="h-7 w-7 p-0 text-muted-foreground hover:text-primary transition-colors"
              title="复制歌单链接"
              @click="copyTaskUrl(task.url)"
            >
              <Copy class="h-3.5 w-3.5" />
            </Button>

            <Popconfirm
              :title="task.status === 'running' ? '终止并移除该任务？' : (task.status === 'pending' ? '取消排队任务？' : '删除该任务记录？')"
              :description="task.status === 'running' ? '已入库的音乐保留，当前进程将被终止并从列表中移除。' : '该任务将从列表中彻底移除。'"
              :confirmText="task.status === 'running' ? '终止并移除' : '删除'"
              :danger="true"
              side="bottom"
              align="end"
              @confirm="handleCancelTask(task)"
            >
              <Button
                variant="ghost"
                size="sm"
                class="h-7 w-7 p-0 text-muted-foreground hover:text-destructive transition-colors"
                :title="task.status === 'running' ? '终止任务' : (task.status === 'pending' ? '取消任务' : '删除记录')"
              >
                <Trash2 class="h-3.5 w-3.5" />
              </Button>
            </Popconfirm>
          </div>
        </div>
      </div>
    </Card>

    <!-- 可折叠实时终端运行记录 -->
    <Card v-if="showLogs" class="overflow-hidden p-0 border-border/80 shadow-sm">
      <div class="flex items-center justify-between border-b border-border px-3.5 py-2.5 bg-[hsl(var(--surface-inset)/.6)]">
        <div class="flex items-center gap-2">
          <Terminal class="h-3.5 w-3.5 text-primary" />
          <span class="text-xs font-bold text-foreground">实时执行记录</span>
          <span class="text-[10px] font-mono text-muted-foreground">共 {{ logs.length }} 行</span>
        </div>
        <div class="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            class="h-6 px-2 text-[10px] text-muted-foreground hover:text-foreground"
            @click="logs.length = 0"
          >
            清空显示
          </Button>
          <Button
            variant="ghost"
            size="sm"
            class="h-6 px-2 text-[10px]"
            :class="autoScrollLogs ? 'text-primary font-bold' : 'text-muted-foreground'"
            @click="autoScrollLogs = !autoScrollLogs"
          >
            自动滚动: {{ autoScrollLogs ? '开' : '关' }}
          </Button>
        </div>
      </div>

      <div
        ref="logContainerRef"
        class="h-52 sm:h-64 overflow-y-auto bg-[hsl(var(--surface-inset))] p-3 font-mono text-[10.5px] sm:text-[11px] leading-5 custom-scrollbar"
      >
        <div v-if="logs.length === 0" class="flex h-full flex-col items-center justify-center text-center text-muted-foreground">
          <Terminal class="h-5 w-5 opacity-40 mb-1" />
          <p class="text-xs">等待任务产生日志输出…</p>
        </div>
        <div v-for="(line, idx) in logs" :key="idx" class="break-all">
          <span class="mr-2 sm:mr-3 select-none text-muted-foreground/45">{{ String(idx + 1).padStart(3, '0') }}</span>
          <span v-if="line.includes('✅')" class="text-success">{{ line }}</span>
          <span v-else-if="line.includes('⚠️') || line.includes('warning')" class="text-warning">{{ line }}</span>
          <span v-else-if="line.includes('❌') || line.includes('STDERR') || line.includes('Error')" class="text-destructive">{{ line }}</span>
          <span v-else-if="line.includes('==')" class="text-primary">{{ line }}</span>
          <span v-else class="text-muted-foreground">{{ line }}</span>
        </div>
      </div>
    </Card>
  </div>
</template>
