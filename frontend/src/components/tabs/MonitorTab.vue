<script setup lang="ts">
import { computed } from 'vue';
import type { TaskState } from '../../types';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Popconfirm } from '@/components/ui/popconfirm';
import { Card } from '@/components/ui/card';
import {
  Disc3,
  Plus,
  Square,
  Check,
  ArrowDownToLine,
  RefreshCw,
  XCircle,
  Terminal,
  Clock3,
  Layers3,
  Radio,
  Music2,
  Activity,
} from 'lucide-vue-next';

const props = defineProps<{
  task: TaskState;
  logs: string[];
}>();

const emit = defineEmits<{
  (e: 'open-task-modal'): void;
  (e: 'stop-task'): void;
}>();

const processedCount = computed(() =>
  (props.task.reused_count || 0) + (props.task.downloaded_count || 0) + (props.task.failed_count || 0)
);

const progressPercent = computed(() => {
  if (!props.task.total) return 0;
  return Math.min(100, Math.round((processedCount.value / props.task.total) * 100));
});

const isRunning = computed(() => ['downloading', 'parsing', 'finalizing'].includes(props.task.status));

const statusBadge = computed(() => {
  switch (props.task.status) {
    case 'parsing': return { text: '正在解析', variant: 'amber' as const };
    case 'downloading': return { text: '同步进行中', variant: 'success' as const };
    case 'finalizing': return { text: '正在入库', variant: 'brand' as const };
    case 'success': return { text: '同步完成', variant: 'success' as const };
    case 'failed': return { text: '任务异常', variant: 'destructive' as const };
    case 'stopped': return { text: '已中止', variant: 'default' as const };
    default: return { text: '待命', variant: 'outline' as const };
  }
});

const metrics = computed(() => [
  { label: '任务曲目', value: props.task.total || 0, hint: '队列总量', icon: Layers3, tone: 'text-slate-300', box: 'bg-slate-500/10' },
  { label: '本地复用', value: props.task.reused_count || 0, hint: '无需下载', icon: Check, tone: 'text-sky-400', box: 'bg-sky-500/10' },
  { label: '新增入库', value: props.task.downloaded_count || 0, hint: '下载完成', icon: ArrowDownToLine, tone: 'text-emerald-400', box: 'bg-emerald-500/10' },
  { label: '处理失败', value: props.task.failed_count || 0, hint: '需要关注', icon: XCircle, tone: 'text-rose-400', box: 'bg-rose-500/10' },
]);

const updatedTime = computed(() => {
  if (!props.task.updated_at) return '--:--:--';
  return new Date(props.task.updated_at).toLocaleTimeString('zh-CN', { hour12: false });
});
</script>

<template>
  <div class="space-y-5">
    <div class="grid gap-5 xl:grid-cols-[minmax(0,1.65fr)_minmax(320px,.8fr)]">
      <Card class="surface-panel relative overflow-hidden border-white/[0.075] p-0">
        <div class="pointer-events-none absolute -right-20 -top-28 h-64 w-64 rounded-full bg-primary/[0.07] blur-3xl" />
        <div class="relative p-5 sm:p-7">
          <div class="flex flex-col justify-between gap-6 sm:flex-row sm:items-start">
            <div class="flex min-w-0 items-center gap-4">
              <div class="relative flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl border border-white/[0.08] bg-black/25">
                <Disc3 class="h-8 w-8 text-slate-500" :class="{ 'animate-spin-slow text-primary': isRunning }" />
                <span class="absolute h-2 w-2 rounded-full" :class="isRunning ? 'bg-primary' : 'bg-slate-700'" />
              </div>
              <div class="min-w-0">
                <div class="mb-2 flex flex-wrap items-center gap-2">
                  <span class="section-label">Current pipeline</span>
                  <Badge :variant="statusBadge.variant" class="text-[10px]">{{ statusBadge.text }}</Badge>
                </div>
                <h3 class="truncate text-xl font-semibold tracking-[-0.025em] text-white sm:text-2xl">
                  {{ task.playlist_name || '等待任务中...' }}
                </h3>
                <div class="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-slate-500">
                  <span class="flex items-center gap-1.5"><Radio class="h-3 w-3" />{{ task.platform || 'TRIM Music' }}</span>
                  <span class="flex items-center gap-1.5"><Music2 class="h-3 w-3" />{{ task.target === 'public' ? '公共歌单' : `专属 · ${task.user}` }}</span>
                  <span class="flex items-center gap-1.5"><Clock3 class="h-3 w-3" />更新于 {{ updatedTime }}</span>
                </div>
              </div>
            </div>

            <div class="flex shrink-0 items-center gap-2">
              <Popconfirm
                v-if="isRunning"
                title="中止当前下载任务？"
                description="已下载入库的曲目将保留，未完成曲目不再继续。"
                confirmText="中止任务"
                :danger="true"
                side="bottom"
                align="end"
                @confirm="emit('stop-task')"
              >
                <Button variant="destructiveOutline" size="default">
                  <Square class="h-3.5 w-3.5 fill-current" />中止任务
                </Button>
              </Popconfirm>
              <Button variant="brand" size="default" @click="emit('open-task-modal')">
                <Plus class="h-4 w-4" />新建同步
              </Button>
            </div>
          </div>

          <div class="mt-7 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <div v-for="metric in metrics" :key="metric.label" class="metric-card">
              <div class="flex items-center justify-between">
                <span class="text-[11px] text-slate-500">{{ metric.label }}</span>
                <span class="flex h-7 w-7 items-center justify-center rounded-lg" :class="[metric.box, metric.tone]">
                  <component :is="metric.icon" class="h-3.5 w-3.5" />
                </span>
              </div>
              <div class="mt-3 text-2xl font-semibold tracking-[-0.04em] text-white">{{ metric.value }}</div>
              <div class="mt-1 text-[10px] text-slate-600">{{ metric.hint }}</div>
            </div>
          </div>

          <div class="mt-6 rounded-xl border border-white/[0.055] bg-black/15 p-4">
            <div class="mb-3 flex items-center justify-between">
              <div>
                <p class="text-[11px] font-medium text-slate-300">同步进度</p>
                <p class="mt-0.5 text-[10px] text-slate-600">已处理 {{ processedCount }} / {{ task.total || 0 }} 首</p>
              </div>
              <span class="font-mono text-sm font-semibold text-primary">{{ progressPercent }}%</span>
            </div>
            <Progress :model-value="progressPercent" class="h-1.5 border-0 bg-white/[0.06]" />
          </div>
        </div>
      </Card>

      <Card class="surface-panel flex min-h-[302px] flex-col p-0">
        <div class="flex items-center justify-between border-b border-white/[0.06] px-5 py-4">
          <div>
            <p class="section-label">Now processing</p>
            <p class="mt-1 text-xs font-medium text-slate-300">当前曲目</p>
          </div>
          <span v-if="task.current_track" class="flex items-center gap-1.5 text-[10px] text-primary">
            <RefreshCw class="h-3 w-3 animate-spin" />实时处理
          </span>
          <Badge v-else variant="outline" class="text-[9px]">空闲</Badge>
        </div>

        <div v-if="task.current_track" class="flex flex-1 flex-col justify-between p-5">
          <div class="flex items-center gap-4">
            <img
              :src="task.current_track.cover || 'https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=400&q=80'"
              class="h-20 w-20 shrink-0 rounded-2xl border border-white/[0.08] object-cover shadow-xl"
              alt="歌曲封面"
            />
            <div class="min-w-0">
              <h4 class="truncate text-base font-semibold text-white">{{ task.current_track.title }}</h4>
              <p class="mt-1 truncate text-xs text-slate-500">{{ task.current_track.artist }}</p>
              <p class="mt-3 truncate text-[10px] font-medium text-primary">{{ task.current_track.step || '正在处理元数据与音轨...' }}</p>
            </div>
          </div>
          <div class="mt-6 flex items-center gap-2 rounded-xl border border-primary/10 bg-primary/[0.045] p-3 text-[10px] text-emerald-300/80">
            <Activity class="h-3.5 w-3.5" />流水线正在持续写入实时状态
          </div>
        </div>

        <div v-else class="flex flex-1 flex-col items-center justify-center px-6 py-10 text-center">
          <div class="flex h-14 w-14 items-center justify-center rounded-2xl border border-dashed border-white/[0.09] bg-white/[0.018]">
            <Disc3 class="h-6 w-6 text-slate-700" />
          </div>
          <p class="mt-4 text-xs font-medium text-slate-400">等待下一首曲目</p>
          <p class="mt-1.5 max-w-[220px] text-[10px] leading-relaxed text-slate-600">创建同步任务后，这里会显示正在处理的音乐与当前步骤。</p>
        </div>
      </Card>
    </div>

    <Card class="surface-panel overflow-hidden p-0">
      <div class="flex items-center justify-between border-b border-white/[0.06] px-5 py-3.5">
        <div class="flex items-center gap-3">
          <span class="flex h-8 w-8 items-center justify-center rounded-lg bg-white/[0.035] text-slate-400">
            <Terminal class="h-4 w-4" />
          </span>
          <div>
            <p class="text-[11px] font-medium text-slate-300">实时事件流</p>
            <p class="mt-0.5 text-[9px] uppercase tracking-[0.14em] text-slate-600">SSE terminal</p>
          </div>
        </div>
        <div class="flex items-center gap-2 text-[10px] text-slate-600">
          <span class="h-1.5 w-1.5 rounded-full bg-emerald-400" />{{ logs.length }} 条事件
        </div>
      </div>
      <div class="h-60 overflow-y-auto bg-black/20 p-5 font-mono text-[11px] leading-6">
        <div v-if="logs.length === 0" class="flex h-full flex-col items-center justify-center text-center">
          <Terminal class="h-5 w-5 text-slate-700" />
          <p class="mt-3 text-slate-600">控制台已就绪，等待流水线事件</p>
        </div>
        <div v-for="(line, idx) in logs" :key="idx" class="break-all">
          <span class="mr-3 select-none text-slate-700">{{ String(idx + 1).padStart(3, '0') }}</span>
          <span v-if="line.includes('✅')" class="text-emerald-400">{{ line }}</span>
          <span v-else-if="line.includes('⚠️') || line.includes('warning')" class="text-amber-400">{{ line }}</span>
          <span v-else-if="line.includes('❌') || line.includes('STDERR') || line.includes('Error')" class="text-rose-400">{{ line }}</span>
          <span v-else-if="line.includes('==')" class="text-sky-400">{{ line }}</span>
          <span v-else class="text-slate-400">{{ line }}</span>
        </div>
      </div>
    </Card>
  </div>
</template>

