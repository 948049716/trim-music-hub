<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue';
import type { TaskState, QueueTask, CurrentUser, TaskTrack } from '../../types';
import { api } from '@/api';
import { showToast } from '@/composables/useToast';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Popconfirm } from '@/components/ui/popconfirm';
import { Card } from '@/components/ui/card';
import { SpringTabs, type SpringTabItem } from '@/components/ui/tabs';
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
  ChevronDown,
  User,
  Copy,
  Play,
  Loader2,
  Disc3,
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

// 展开状态
const isRunningDetailExpanded = ref(true);
const expandedTaskIds = ref<Set<string>>(new Set());

function toggleTaskExpand(taskId: string) {
  const next = new Set(expandedTaskIds.value);
  if (next.has(taskId)) {
    next.delete(taskId);
  } else {
    next.add(taskId);
  }
  expandedTaskIds.value = next;
}

// Drag & Drop State
const draggedTaskId = ref<string | null>(null);
const dragOverTaskId = ref<string | null>(null);
const resumingTaskId = ref<string | null>(null);

const activeQueue = computed(() => {
  const list = props.queue || [];
  return [...list].sort((a, b) => {
    // Running first, then pending sorted by order, then others by created_at desc
    if (a.status === 'running' || a.status === 'downloading') return -1;
    if (b.status === 'running' || b.status === 'downloading') return 1;
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
    return activeQueue.value.filter(t => t.status === 'pending' || t.status === 'running' || t.status === 'downloading');
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
    running: list.filter(t => t.status === 'running' || t.status === 'downloading').length,
    pending: list.filter(t => t.status === 'pending').length,
    completed: list.filter(t => ['success', 'failed', 'stopped'].includes(t.status)).length,
  };
});

const filterTabs = computed<SpringTabItem<QueueFilter>[]>(() => [
  { value: 'all', label: '全部', badge: counts.value.total },
  {
    value: 'active',
    label: '执行与等待',
    badge: counts.value.running + counts.value.pending,
    badgeClass: counts.value.running + counts.value.pending > 0 ? 'bg-primary/20 text-primary font-bold animate-pulse' : undefined,
  },
  { value: 'completed', label: '已完成', badge: counts.value.completed },
]);

const isRunning = computed(() => ['downloading', 'parsing', 'finalizing', 'running'].includes(props.task.status));

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
    currentTrack: props.task.current_track,
    tracks: props.task.tracks || [],
  };
});

// 计算当前进行中单曲在总歌单中的序号
const currentTrackOrder = computed(() => {
  if (!runningTaskDetails.value) return 1;
  const cur = props.task.current_track;
  if (!cur) return Math.min(runningTaskDetails.value.processed + 1, runningTaskDetails.value.total || 1);
  const tracks = props.task.tracks || [];
  const foundIdx = tracks.findIndex(t => t.title === cur.title && t.artist === cur.artist);
  if (foundIdx >= 0) return foundIdx + 1;
  return Math.min(runningTaskDetails.value.processed + 1, runningTaskDetails.value.total || 1);
});

// 曲目明细筛选
type TrackFilter = 'all' | 'downloading' | 'downloaded' | 'reused' | 'failed';
const trackFilter = ref<TrackFilter>('all');

const filteredRunningTracks = computed(() => {
  const tracks = props.task.tracks || [];
  if (trackFilter.value === 'downloading') {
    return tracks.filter(t => t.status === 'downloading' || (props.task.current_track && t.title === props.task.current_track.title));
  }
  if (trackFilter.value === 'downloaded') {
    return tracks.filter(t => t.status === 'downloaded');
  }
  if (trackFilter.value === 'reused') {
    return tracks.filter(t => t.status === 'reused');
  }
  if (trackFilter.value === 'failed') {
    return tracks.filter(t => t.status === 'failed');
  }
  return tracks;
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

function getTaskLiveSpeed(task: QueueTask) {
  if (task.status === 'running' || task.status === 'downloading') {
    return props.task.speed || task.speed || '';
  }
  return task.speed || '';
}

function getTaskCurrentTrack(task: QueueTask) {
  if (task.status === 'running' || task.status === 'downloading') {
    return props.task.current_track || task.current_track;
  }
  return task.current_track;
}

function getTaskTracks(task: QueueTask): TaskTrack[] {
  if (task.status === 'running' || task.status === 'downloading') {
    if (props.task.tracks && props.task.tracks.length > 0) return props.task.tracks;
  }
  return task.tracks || [];
}

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

async function handleResumeTask(task: QueueTask) {
  resumingTaskId.value = task.id;
  try {
    const res = await api.resumeTask(task.id);
    if (res.ok) {
      showToast(res.message || '任务已恢复，正在继续下载', 'success');
      emit('refresh-queue');
    } else {
      showToast(res.error || '恢复任务失败', 'error');
    }
  } catch (e: any) {
    showToast(e.message || '网络异常', 'error');
  } finally {
    resumingTaskId.value = null;
  }
}

async function handleStopCurrentTask() {
  try {
    const res = await api.stopTask();
    if (res.ok) {
      showToast('任务已中止', 'info');
      emit('refresh-queue');
    } else {
      showToast(res.error || '中止任务失败', 'error');
    }
  } catch (e: any) {
    showToast(e.message || '网络异常', 'error');
  }
}

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

function getTrackStatusBadge(status: string) {
  switch (status) {
    case 'downloading': return { text: '下载中', variant: 'brand' as const, icon: RefreshCw, spin: true };
    case 'downloaded': return { text: '已入库', variant: 'success' as const, icon: CheckCircle2, spin: false };
    case 'reused': return { text: '本地复用', variant: 'info' as const, icon: CheckCircle2, spin: false };
    case 'failed': return { text: '失败', variant: 'destructive' as const, icon: AlertCircle, spin: false };
    case 'pending': return { text: '等待中', variant: 'outline' as const, icon: Clock3, spin: false };
    default: return { text: status, variant: 'outline' as const, icon: Clock3, spin: false };
  }
}

function formatTaskTime(isoString?: string) {
  if (!isoString) return '--:--';
  const d = new Date(isoString);
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

watch(() => props.logs.length, () => {
  if (autoScrollLogs.value && logContainerRef.value) {
    nextTick(() => {
      if (logContainerRef.value) {
        logContainerRef.value.scrollTop = logContainerRef.value.scrollHeight;
      }
    });
  }
});
</script>

<template>
  <div class="tab-content-container gap-2.5 sm:gap-3">
    <!-- ==================== 顶部状态栏与操作工具条 (固定在顶部，不随列表滚动) ==================== -->
    <div class="flex flex-col gap-2.5 sm:flex-row sm:items-center sm:justify-between shrink-0">
      <!-- 队列统计胶囊与物理弹簧筛选切换 (移动端平铺自适应) -->
      <div class="w-full sm:w-auto">
        <SpringTabs
          v-model="filter"
          :items="filterTabs"
          size="sm"
          variant="default"
          class="w-full sm:w-auto"
        />
      </div>

      <!-- 右侧操作按钮组 (移动端自适应两端或右对齐) -->
      <div class="flex items-center justify-between sm:justify-end gap-2 w-full sm:w-auto">
        <div class="flex items-center gap-1.5">
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
            <Button
              variant="outline"
              size="sm"
              class="h-8 px-2.5 text-xs text-muted-foreground hover:text-foreground gap-1.5 rounded-lg"
            >
              <Trash2 class="h-3.5 w-3.5" />
              <span>清空完成</span>
            </Button>
          </Popconfirm>

          <Button
            variant="outline"
            size="sm"
            class="h-8 px-2.5 text-xs gap-1.5 rounded-lg transition-colors"
            :class="{ 'bg-primary/10 text-primary border-primary/30 font-semibold': showLogs }"
            @click="showLogs = !showLogs"
          >
            <Terminal class="h-3.5 w-3.5" />
            <span>{{ showLogs ? '收起日志' : '实时日志' }}</span>
            <span v-if="logs.length" class="text-[10px] text-muted-foreground font-mono">({{ logs.length }})</span>
          </Button>
        </div>

        <Button
          variant="brand"
          size="sm"
          class="h-8 px-3 text-xs font-semibold gap-1.5 shadow-sm active:scale-95 rounded-lg"
          @click="emit('open-task-modal')"
        >
          <Plus class="h-3.5 w-3.5" />
          <span>新建任务</span>
        </Button>
      </div>
    </div>

    <!-- ==================== 主内容滚动视口 (保证任务队列流畅滚动) ==================== -->
    <div
      class="flex-1 min-h-0 overflow-y-auto custom-scrollbar space-y-3 sm:space-y-4 pb-4 sm:pb-6 pr-0.5"
      style="-webkit-overflow-scrolling: touch;"
    >

    <!-- ==================== 正在执行任务卡片与实时详细面板 ==================== -->
    <div
      v-if="runningTaskDetails"
      class="relative overflow-hidden rounded-xl border border-primary/35 bg-card/90 p-3 sm:p-4 shadow-sm backdrop-blur-sm transition-all"
    >
      <!-- 主标题与操作行 -->
      <div class="flex items-center justify-between gap-3">
        <div class="flex items-center gap-2.5 sm:gap-3 min-w-0">
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
            <div class="flex items-center gap-1.5 sm:gap-2 flex-wrap">
              <Badge variant="brand" class="text-[10px] py-0 px-1.5 h-4.5 gap-1 shrink-0">
                <span class="inline-block h-1.5 w-1.5 rounded-full bg-primary animate-pulse" />
                {{ props.task.status === 'downloading' ? '下载中' : (props.task.status === 'parsing' ? '解析中' : (props.task.status === 'finalizing' ? '入库中' : '正在执行')) }}
              </Badge>
              <h3 class="text-xs sm:text-sm font-bold text-foreground truncate max-w-[160px] sm:max-w-md">
                {{ runningTaskDetails.title }}
              </h3>
              <span
                v-if="runningTaskDetails.speed"
                class="text-[10px] font-mono font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-full shrink-0 flex items-center gap-1 animate-pulse"
              >
                ⚡ {{ runningTaskDetails.speed }}
              </span>
            </div>
            <p class="mt-0.5 text-[11px] text-muted-foreground truncate font-mono flex items-center gap-1.5">
              <span class="truncate">{{ runningTaskDetails.step }}</span>
            </p>
          </div>
        </div>

        <!-- 卡片右上角快捷操作 -->
        <div class="flex items-center gap-1.5 shrink-0">
          <Button
            variant="ghost"
            size="sm"
            class="h-7 px-2 text-xs gap-1 text-primary hover:bg-primary/10"
            @click="isRunningDetailExpanded = !isRunningDetailExpanded"
          >
            <span>{{ isRunningDetailExpanded ? '收起详细' : '执行详细' }}</span>
            <ChevronDown
              class="h-3.5 w-3.5 transition-transform duration-200"
              :class="{ 'rotate-180': isRunningDetailExpanded }"
            />
          </Button>

          <Popconfirm
            title="终止当前运行任务？"
            description="已入库的音乐文件将保留，当前正在进行的下载将被中止。"
            confirmText="终止任务"
            :danger="true"
            side="bottom"
            align="end"
            @confirm="emit('stop-task')"
          >
            <Button variant="destructiveOutline" size="sm" class="h-7 px-2 text-xs gap-1">
              <Square class="h-3 w-3 fill-current" />
              <span class="hidden sm:inline">终止</span>
            </Button>
          </Popconfirm>
        </div>
      </div>

      <!-- 整体进度条 -->
      <div class="mt-2.5 flex items-center gap-3">
        <Progress :model-value="runningTaskDetails.percent" class="h-1.5 bg-muted flex-1" />
        <span class="text-xs font-bold tabular-nums text-primary font-mono shrink-0">
          {{ runningTaskDetails.percent }}% ({{ runningTaskDetails.processed }}/{{ runningTaskDetails.total }})
        </span>
      </div>

      <!-- 展开详细内容：当前歌曲进度、实时网速与曲目清单 -->
      <div v-if="isRunningDetailExpanded" class="mt-3.5 pt-3 border-t border-border/60 space-y-3">
        <!-- 1. 当前进行中的具体单曲实时卡片 -->
        <div class="rounded-xl border border-primary/25 bg-primary/5 p-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div class="flex items-center gap-3 min-w-0">
            <div class="relative h-12 w-12 shrink-0 rounded-lg overflow-hidden border border-primary/30 bg-muted/80 shadow-xs flex items-center justify-center">
              <img
                v-if="runningTaskDetails.currentTrack?.cover"
                :src="runningTaskDetails.currentTrack.cover"
                class="h-full w-full object-cover"
                alt="当前歌曲封面"
              />
              <Disc3 v-else class="h-6 w-6 text-primary animate-spin" />
              <div class="absolute inset-0 bg-primary/10 flex items-center justify-center pointer-events-none">
                <div class="h-2 w-2 rounded-full bg-primary animate-ping" />
              </div>
            </div>

            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2 flex-wrap">
                <Badge variant="outline" class="text-[9px] py-0 px-1.5 h-4 border-primary/40 text-primary font-mono font-semibold">
                  第 {{ currentTrackOrder }} / {{ runningTaskDetails.total }} 首
                </Badge>
                <h4 class="text-xs sm:text-sm font-bold text-foreground truncate">
                  {{ runningTaskDetails.currentTrack?.title || '正在抓取音频流...' }}
                </h4>
                <span class="text-xs text-muted-foreground truncate">
                  - {{ runningTaskDetails.currentTrack?.artist || 'TRIM Sync' }}
                </span>
              </div>
              <p class="mt-1 text-[11px] text-muted-foreground flex items-center gap-1.5">
                <Loader2 class="h-3 w-3 animate-spin text-primary shrink-0" />
                <span class="font-mono text-foreground/80 truncate">
                  {{ runningTaskDetails.currentTrack?.step || '正在解析音频流并同步元数据...' }}
                </span>
              </p>
            </div>
          </div>

          <div class="flex items-center gap-2 shrink-0 self-end sm:self-auto">
            <div class="flex flex-col items-end">
              <span class="text-[10px] text-muted-foreground">实时速度</span>
              <span class="text-xs font-bold font-mono text-primary flex items-center gap-1">
                ⚡ {{ runningTaskDetails.speed || '测速中...' }}
              </span>
            </div>
          </div>
        </div>

        <!-- 2. 四维实时执行指标条 -->
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center">
          <div class="p-2 rounded-lg bg-card border border-border/70 flex flex-col items-center">
            <span class="text-[10px] text-muted-foreground">实时网速</span>
            <span class="mt-0.5 text-xs font-bold font-mono text-primary truncate max-w-full">
              {{ runningTaskDetails.speed || '测速中...' }}
            </span>
          </div>
          <div class="p-2 rounded-lg bg-card border border-border/70 flex flex-col items-center">
            <span class="text-[10px] text-muted-foreground">已下载入库</span>
            <span class="mt-0.5 text-xs font-bold font-mono text-success">
              {{ runningTaskDetails.downloaded }} 首
            </span>
          </div>
          <div class="p-2 rounded-lg bg-card border border-border/70 flex flex-col items-center">
            <span class="text-[10px] text-muted-foreground">本地曲库复用</span>
            <span class="mt-0.5 text-xs font-bold font-mono text-info">
              {{ runningTaskDetails.reused }} 首
            </span>
          </div>
          <div class="p-2 rounded-lg bg-card border border-border/70 flex flex-col items-center">
            <span class="text-[10px] text-muted-foreground">失败 / 跳过</span>
            <span class="mt-0.5 text-xs font-bold font-mono" :class="runningTaskDetails.failed > 0 ? 'text-destructive' : 'text-muted-foreground'">
              {{ runningTaskDetails.failed }} 首
            </span>
          </div>
        </div>

        <!-- 3. 曲目级逐首明细列表 -->
        <div v-if="runningTaskDetails.tracks && runningTaskDetails.tracks.length > 0" class="space-y-2">
          <div class="flex items-center justify-between gap-2 flex-wrap pt-1">
            <div class="flex items-center gap-1.5">
              <ListMusic class="h-3.5 w-3.5 text-primary" />
              <span class="text-xs font-bold text-foreground">曲目执行明细</span>
              <span class="text-[10px] text-muted-foreground font-mono">({{ runningTaskDetails.tracks.length }} 首)</span>
            </div>

            <div class="flex items-center gap-1 text-[10px]">
              <button
                type="button"
                class="px-2 py-0.5 rounded transition-colors"
                :class="trackFilter === 'all' ? 'bg-primary text-primary-foreground font-semibold' : 'text-muted-foreground hover:bg-muted'"
                @click="trackFilter = 'all'"
              >
                全部
              </button>
              <button
                type="button"
                class="px-2 py-0.5 rounded transition-colors"
                :class="trackFilter === 'downloading' ? 'bg-primary text-primary-foreground font-semibold' : 'text-muted-foreground hover:bg-muted'"
                @click="trackFilter = 'downloading'"
              >
                进行中
              </button>
              <button
                type="button"
                class="px-2 py-0.5 rounded transition-colors"
                :class="trackFilter === 'downloaded' ? 'bg-primary text-primary-foreground font-semibold' : 'text-muted-foreground hover:bg-muted'"
                @click="trackFilter = 'downloaded'"
              >
                已入库
              </button>
              <button
                type="button"
                class="px-2 py-0.5 rounded transition-colors"
                :class="trackFilter === 'reused' ? 'bg-primary text-primary-foreground font-semibold' : 'text-muted-foreground hover:bg-muted'"
                @click="trackFilter = 'reused'"
              >
                复用
              </button>
              <button
                type="button"
                class="px-2 py-0.5 rounded transition-colors"
                :class="trackFilter === 'failed' ? 'bg-primary text-primary-foreground font-semibold' : 'text-muted-foreground hover:bg-muted'"
                @click="trackFilter = 'failed'"
              >
                失败
              </button>
            </div>
          </div>

          <div class="max-h-56 overflow-y-auto rounded-lg border border-border/80 bg-background/60 divide-y divide-border/50 custom-scrollbar">
            <div
              v-for="(tr, idx) in filteredRunningTracks"
              :key="idx"
              class="flex items-center justify-between gap-2 px-3 py-2 text-xs transition-colors hover:bg-muted/30"
              :class="{ 'bg-primary/5': tr.status === 'downloading' || (props.task.current_track && tr.title === props.task.current_track.title) }"
            >
              <div class="flex items-center gap-2 min-w-0 flex-1">
                <span class="text-[10px] font-mono text-muted-foreground w-6 shrink-0">
                  #{{ String(idx + 1).padStart(2, '0') }}
                </span>
                <span class="font-medium text-foreground truncate max-w-[160px] sm:max-w-xs">
                  {{ tr.title }}
                </span>
                <span class="text-muted-foreground truncate hidden sm:inline">
                  - {{ tr.artist }}
                </span>
                <Badge
                  v-if="tr.quality"
                  variant="outline"
                  class="text-[9px] py-0 px-1 font-mono uppercase h-4 shrink-0"
                >
                  {{ tr.quality }}
                </Badge>
                <span v-if="tr.adjustment_note" class="text-[9px] text-amber-500 truncate hidden md:inline">
                  ({{ tr.adjustment_note }})
                </span>
              </div>

              <div class="shrink-0 flex items-center gap-1.5">
                <Badge
                  :variant="getTrackStatusBadge(tr.status).variant"
                  class="text-[10px] py-0 px-1.5 h-4.5 gap-1 font-medium"
                >
                  <component
                    :is="getTrackStatusBadge(tr.status).icon"
                    class="h-2.5 w-2.5"
                    :class="{ 'animate-spin': getTrackStatusBadge(tr.status).spin }"
                  />
                  <span>{{ getTrackStatusBadge(tr.status).text }}</span>
                </Badge>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ==================== 任务队列列表与调度器 ==================== -->
    <Card class="overflow-hidden p-0 border-border/80 shadow-sm">
      <div class="sticky top-0 z-10 px-3.5 py-2.5 sm:px-4 sm:py-3 border-b border-border/70 flex items-center justify-between bg-card/95 backdrop-blur-md">
        <div class="flex items-center gap-2 min-w-0">
          <Layers class="h-4 w-4 text-primary shrink-0" />
          <h3 class="text-xs sm:text-sm font-bold text-foreground">任务队列</h3>
          <span class="text-[10px] text-muted-foreground hidden sm:inline">按住手柄拖拽可调整排队顺序</span>
        </div>
        <div class="flex items-center gap-2 text-[11px] text-muted-foreground font-mono shrink-0">
          <span>共 {{ filteredQueue.length }} 项</span>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-if="filteredQueue.length === 0" class="py-12 sm:py-14 text-center px-4">
        <div class="inline-grid h-12 w-12 place-items-center rounded-2xl bg-muted/60 text-muted-foreground mb-3">
          <Layers class="h-6 w-6 opacity-60" />
        </div>
        <p class="text-xs sm:text-sm font-semibold text-foreground">当前没有待处理或运行的任务</p>
        <p class="mt-1 text-[11px] text-muted-foreground max-w-xs mx-auto">
          点击右上角「新建任务」导入歌单，或在「导歌」中粘贴歌单链接与全网搜歌。
        </p>
        <Button variant="brand" size="sm" class="mt-4 h-8 text-xs gap-1.5 rounded-lg" @click="emit('open-task-modal')">
          <Plus class="h-3.5 w-3.5" />新建任务
        </Button>
      </div>

      <!-- 任务列表 (针对移动端 381px 及桌面端全面优化排版) -->
      <div v-else class="divide-y divide-border/60">
        <div
          v-for="task in filteredQueue"
          :key="task.id"
          class="group relative p-2.5 sm:p-3 transition-colors select-none"
          :class="[
            task.status === 'running' || task.status === 'downloading' ? 'bg-primary/5' : 'hover:bg-muted/40',
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
          <!-- 结构化任务卡片布局 (保证移动端 381px 下不拥挤、不截断、操作舒适) -->
          <div class="flex items-start gap-2.5 sm:gap-3">
            <!-- 左侧：拖拽手柄与封面 -->
            <div class="flex items-center gap-1.5 shrink-0 pt-0.5">
              <template v-if="task.status === 'pending'">
                <div
                  class="cursor-grab active:cursor-grabbing p-1 text-muted-foreground/50 hover:text-foreground transition-colors rounded"
                  title="拖拽调整执行顺序"
                >
                  <GripVertical class="h-4 w-4" />
                </div>
              </template>
              <div v-else class="w-4 grid place-items-center text-muted-foreground/35">
                <span class="inline-block h-1.5 w-1.5 rounded-full bg-border" />
              </div>

              <div class="relative h-10 w-10 sm:h-11 sm:w-11 shrink-0 rounded-lg overflow-hidden border border-border/80 bg-muted grid place-items-center">
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
            </div>

            <!-- 主内容区域 (三行式设计) -->
            <div class="min-w-0 flex-1">
              <!-- 第一行：序号 + 标题 + 状态徽章 -->
              <div class="flex items-center justify-between gap-2">
                <div class="flex items-center gap-1.5 min-w-0 flex-1">
                  <span
                    v-if="task.order"
                    class="text-[10px] font-mono font-bold text-muted-foreground bg-muted/80 px-1 py-0.2 rounded shrink-0"
                  >
                    #{{ task.order }}
                  </span>
                  <h4 class="truncate text-xs sm:text-sm font-semibold text-foreground">
                    {{ task.title }}
                  </h4>
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
              </div>

              <!-- 第二行：标签属性 + 进度指标 + 实时网速 -->
              <div class="mt-1 flex items-center gap-1.5 text-[10px] text-muted-foreground font-mono flex-wrap">
                <Badge variant="outline" class="text-[9px] py-0 px-1.5 h-4">
                  {{ task.type === 'single' ? '单曲' : '歌单' }}
                </Badge>
                <Badge v-if="task.quality" variant="secondary" class="text-[9px] py-0 px-1.5 h-4 font-mono uppercase">
                  {{ task.quality }}
                </Badge>
                <span v-if="task.target" class="text-muted-foreground/80">
                  {{ task.target === 'public' ? '公共曲库' : '专属' }}
                </span>
                <span v-if="task.total > 0" class="text-primary font-semibold">
                  进度 {{ getTaskProcessed(task) }}/{{ task.total }}
                </span>
                <span
                  v-if="getTaskLiveSpeed(task)"
                  class="text-primary font-bold bg-primary/10 px-1.5 py-0.2 rounded animate-pulse"
                >
                  ⚡ {{ getTaskLiveSpeed(task) }}
                </span>
              </div>

              <!-- 第三行：时间/当前歌曲提示 + 右侧操作按钮组 -->
              <div class="mt-2 flex items-center justify-between gap-2 pt-1 border-t border-border/40">
                <div class="min-w-0 flex-1 text-[10px] text-muted-foreground truncate">
                  <span v-if="task.status === 'running' || task.status === 'downloading'" class="text-primary font-medium flex items-center gap-1 truncate">
                    <Loader2 class="h-3 w-3 animate-spin shrink-0" />
                    <span class="truncate">
                      {{ getTaskCurrentTrack(task)?.title ? `处理中: ${getTaskCurrentTrack(task)?.title}` : '任务同步中...' }}
                    </span>
                  </span>
                  <span v-else>
                    {{ formatTaskTime(task.created_at) }}
                    <span v-if="currentUser?.isAdmin && task.owner_user"> · {{ task.owner_user }}</span>
                  </span>
                </div>

                <!-- 操作按钮组 -->
                <div class="flex items-center gap-1 shrink-0" @click.stop>
                  <!-- 展开查看执行详细按钮 -->
                  <Button
                    variant="ghost"
                    size="sm"
                    class="h-7 px-2 text-xs gap-1 text-muted-foreground hover:text-foreground transition-colors"
                    :class="{ 'text-primary font-semibold bg-primary/10': expandedTaskIds.has(task.id) }"
                    title="展开查看执行明细"
                    @click="toggleTaskExpand(task.id)"
                  >
                    <span>详细</span>
                    <ChevronDown
                      class="h-3 w-3 transition-transform duration-200"
                      :class="{ 'rotate-180': expandedTaskIds.has(task.id) }"
                    />
                  </Button>

                  <!-- 复制歌单链接 -->
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

                  <!-- 继续任务按钮 -->
                  <Button
                    v-if="task.status === 'stopped' || task.status === 'failed'"
                    variant="outline"
                    size="sm"
                    class="h-7 px-2 text-xs gap-1 font-semibold text-primary border-primary/40 bg-primary/10 hover:bg-primary/20 active:scale-95 transition-all shadow-xs"
                    title="从中断位置继续下载"
                    :disabled="resumingTaskId === task.id"
                    @click="handleResumeTask(task)"
                  >
                    <Play v-if="resumingTaskId !== task.id" class="h-3 w-3 fill-current" />
                    <Loader2 v-else class="h-3 w-3 animate-spin" />
                    <span>继续</span>
                  </Button>

                  <!-- 运行中任务中止按钮 -->
                  <Popconfirm
                    v-if="task.status === 'running' || task.status === 'downloading'"
                    title="中止当前任务？"
                    description="已入库的音乐保留，当前下载将被中止，之后可随时继续。"
                    confirmText="中止任务"
                    :danger="true"
                    side="bottom"
                    align="end"
                    @confirm="handleStopCurrentTask"
                  >
                    <Button
                      variant="ghost"
                      size="sm"
                      class="h-7 w-7 p-0 text-amber-500 hover:bg-amber-500/15 transition-colors"
                      title="中止任务"
                    >
                      <Square class="h-3.5 w-3.5 fill-current" />
                    </Button>
                  </Popconfirm>

                  <!-- 移除/彻底删除记录 -->
                  <Popconfirm
                    :title="task.status === 'running' ? '终止并彻底删除该任务？' : (task.status === 'pending' ? '取消排队任务？' : '删除该任务记录？')"
                    :description="task.status === 'running' ? '已入库的音乐保留，当前进程将被终止并从列表中彻底移除。' : '该任务将从列表中彻底移除。'"
                    :confirmText="task.status === 'running' ? '终止并删除' : '删除'"
                    :danger="true"
                    side="bottom"
                    align="end"
                    @confirm="handleCancelTask(task)"
                  >
                    <Button
                      variant="ghost"
                      size="sm"
                      class="h-7 w-7 p-0 text-muted-foreground hover:text-destructive transition-colors"
                      :title="task.status === 'running' ? '彻底删除任务' : (task.status === 'pending' ? '取消任务' : '删除记录')"
                    >
                      <Trash2 class="h-3.5 w-3.5" />
                    </Button>
                  </Popconfirm>
                </div>
              </div>
            </div>
          </div>

          <!-- 单任务内嵌执行明细抽屉面板 -->
          <div
            v-if="expandedTaskIds.has(task.id)"
            class="mt-3 pt-3 border-t border-border/60 space-y-2.5 rounded-lg bg-muted/20 p-2.5 sm:p-3"
          >
            <!-- 运行中特别展示：当前歌曲实时卡片 -->
            <div
              v-if="(task.status === 'running' || task.status === 'downloading') && getTaskCurrentTrack(task)"
              class="rounded-lg border border-primary/30 bg-primary/5 p-2.5 flex items-center justify-between gap-3"
            >
              <div class="flex items-center gap-2.5 min-w-0">
                <div class="relative h-9 w-9 shrink-0 rounded overflow-hidden border border-primary/30 bg-muted grid place-items-center">
                  <img
                    v-if="getTaskCurrentTrack(task)?.cover"
                    :src="getTaskCurrentTrack(task)!.cover"
                    class="h-full w-full object-cover"
                    alt="当前单曲"
                  />
                  <Disc3 v-else class="h-5 w-5 text-primary animate-spin" />
                </div>
                <div class="min-w-0 flex-1">
                  <h5 class="text-xs font-bold text-foreground truncate">
                    {{ getTaskCurrentTrack(task)?.title }}
                    <span class="text-muted-foreground font-normal"> - {{ getTaskCurrentTrack(task)?.artist }}</span>
                  </h5>
                  <p class="text-[10px] text-muted-foreground font-mono truncate">
                    {{ getTaskCurrentTrack(task)?.step || '正在下载音频流...' }}
                  </p>
                </div>
              </div>

              <div v-if="getTaskLiveSpeed(task)" class="shrink-0 text-right">
                <span class="text-[10px] font-mono font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-full">
                  ⚡ {{ getTaskLiveSpeed(task) }}
                </span>
              </div>
            </div>

            <!-- 执行统计指标小结 -->
            <div class="flex items-center justify-between text-[11px] text-muted-foreground font-mono bg-card/60 p-2 rounded border border-border/50 flex-wrap gap-2">
              <span>总曲目: <strong class="text-foreground">{{ task.total || 0 }}</strong> 首</span>
              <span class="text-success">已下载: <strong>{{ task.downloaded_count || 0 }}</strong></span>
              <span class="text-info">本地复用: <strong>{{ task.reused_count || 0 }}</strong></span>
              <span :class="(task.failed_count || 0) > 0 ? 'text-destructive font-bold' : ''">
                失败: <strong>{{ task.failed_count || 0 }}</strong>
              </span>
              <span v-if="getTaskLiveSpeed(task)" class="text-primary font-bold">
                速度: {{ getTaskLiveSpeed(task) }}
              </span>
            </div>

            <!-- 曲目清单预览 -->
            <div v-if="getTaskTracks(task).length > 0" class="space-y-1">
              <span class="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">曲目列表 ({{ getTaskTracks(task).length }})</span>
              <div class="max-h-44 overflow-y-auto rounded border border-border/70 bg-card divide-y divide-border/40 custom-scrollbar text-[11px]">
                <div
                  v-for="(t, i) in getTaskTracks(task)"
                  :key="i"
                  class="flex items-center justify-between gap-2 px-2.5 py-1.5"
                  :class="{ 'bg-primary/10 font-medium': t.status === 'downloading' }"
                >
                  <div class="flex items-center gap-1.5 min-w-0 flex-1">
                    <span class="text-[10px] font-mono text-muted-foreground w-5 shrink-0">#{{ i + 1 }}</span>
                    <span class="truncate text-foreground">{{ t.title }}</span>
                    <span class="text-muted-foreground truncate hidden sm:inline">- {{ t.artist }}</span>
                  </div>
                  <div class="shrink-0 flex items-center gap-1">
                    <Badge :variant="getTrackStatusBadge(t.status).variant" class="text-[9px] py-0 px-1.5 h-4">
                      {{ getTrackStatusBadge(t.status).text }}
                    </Badge>
                  </div>
                </div>
              </div>
            </div>

            <!-- 错误信息 -->
            <div v-if="task.error" class="p-2 rounded bg-destructive/10 text-destructive text-[11px] font-mono">
              错误原因: {{ task.error }}
            </div>
          </div>
        </div>
      </div>
    </Card>

    <!-- ==================== 可折叠实时终端运行记录 ==================== -->
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
  </div>
</template>
