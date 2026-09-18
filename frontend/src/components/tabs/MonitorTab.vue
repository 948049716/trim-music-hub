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
    case 'parsing': return { text: '正在解析', variant: 'warning' as const };
    case 'downloading': return { text: '同步进行中', variant: 'success' as const };
    case 'finalizing': return { text: '正在入库', variant: 'brand' as const };
    case 'success': return { text: '同步完成', variant: 'success' as const };
    case 'failed': return { text: '任务异常', variant: 'destructive' as const };
    case 'stopped': return { text: '已中止', variant: 'default' as const };
    default: return { text: '待命', variant: 'outline' as const };
  }
});

const metrics = computed(() => [
  { label: '任务曲目', value: props.task.total || 0, hint: '队列总量', icon: Layers3, tone: 'text-foreground/85', box: 'bg-muted' },
  { label: '本地复用', value: props.task.reused_count || 0, hint: '无需下载', icon: Check, tone: 'text-info', box: 'bg-info/10' },
  { label: '新增入库', value: props.task.downloaded_count || 0, hint: '下载完成', icon: ArrowDownToLine, tone: 'text-success', box: 'bg-success/10' },
  { label: '处理失败', value: props.task.failed_count || 0, hint: '需要关注', icon: XCircle, tone: 'text-destructive', box: 'bg-destructive/10' },
]);

const updatedTime = computed(() => {
  if (!props.task.updated_at) return '--:--:--';
  return new Date(props.task.updated_at).toLocaleTimeString('zh-CN', { hour12: false });
});
</script>

<template>
  <div class="space-y-4 sm:space-y-5">
    <Card class="relative overflow-hidden p-0">
      <div class="grid lg:grid-cols-[minmax(0,1.55fr)_minmax(280px,.75fr)]">
        <!-- 任务状态与指标区（适配小屏与超小屏） -->
        <section class="relative p-3 sm:p-5 lg:p-7">
          <div class="pointer-events-none absolute right-0 top-0 h-52 w-52 rounded-full bg-primary/10 blur-3xl" />
          
          <div class="relative flex flex-col justify-between gap-4 sm:gap-6 sm:flex-row sm:items-start">
            <div class="flex min-w-0 items-start gap-3 sm:gap-4">
              <!-- 紧凑响应式唱片圆盘 -->
              <div class="relative grid h-12 w-12 sm:h-16 sm:w-16 shrink-0 place-items-center rounded-full border-[4px] sm:border-[6px] border-muted bg-[hsl(var(--surface-inset))] shadow-inner mt-0.5 sm:mt-0">
                <Disc3 class="h-6 w-6 sm:h-8 sm:w-8 text-muted-foreground" :class="{ 'animate-spin-slow text-primary': isRunning }" />
                <span class="absolute h-1.5 w-1.5 sm:h-2 sm:w-2 rounded-full bg-card ring-1 ring-border" />
              </div>
              
              <!-- 任务标题与标签 -->
              <div class="min-w-0 flex-1">
                <div class="mb-1.5 sm:mb-2 flex flex-wrap items-center gap-1.5 sm:gap-2">
                  <Badge :variant="statusBadge.variant" class="text-[10px] sm:text-xs py-0.5 px-2">{{ statusBadge.text }}</Badge>
                  <span class="text-[10px] sm:text-[11px] text-muted-foreground">最后更新 {{ updatedTime }}</span>
                </div>
                <!-- 避免移动端被单行粗暴截断，允许两行优雅展示 -->
                <h3 class="line-clamp-2 text-base font-bold tracking-tight text-foreground sm:text-2xl sm:line-clamp-1 leading-snug">
                  {{ task.playlist_name || '还没有进行中的任务' }}
                </h3>
                <div class="mt-1.5 sm:mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] sm:text-[11px] text-muted-foreground">
                  <span class="flex items-center gap-1"><Radio class="h-3 w-3" />{{ task.platform || 'TRIM Music' }}</span>
                  <span class="flex items-center gap-1"><Music2 class="h-3 w-3" />{{ task.target === 'public' ? '所有成员可见' : `仅 ${task.user} 可见` }}</span>
                </div>
              </div>
            </div>

            <!-- 操作按钮（移动端自适应紧凑化） -->
            <div class="flex shrink-0 items-center gap-2 w-full sm:w-auto justify-end">
              <Popconfirm v-if="isRunning" title="停止当前任务？" description="已经保存的歌曲会保留，剩余歌曲不再处理。" confirmText="停止任务" :danger="true" side="bottom" align="end" @confirm="emit('stop-task')">
                <Button variant="destructiveOutline" size="sm" class="h-8 px-3 text-xs"><Square class="h-3 w-3 fill-current" />停止</Button>
              </Popconfirm>
              <Button variant="brand" size="sm" class="h-8 sm:h-9 px-3 sm:px-4 text-xs sm:text-sm font-semibold gap-1.5 shadow-sm active:scale-95" @click="emit('open-task-modal')">
                <Plus class="h-3.5 w-3.5 sm:h-4 sm:w-4" />导入歌单
              </Button>
            </div>
          </div>

          <!-- 四宫格指标（小屏紧凑比例，字号协调，不再笨重） -->
          <div class="relative mt-4 sm:mt-6 grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-border/80 bg-border/80 lg:grid-cols-4 shadow-sm">
            <div v-for="metric in metrics" :key="metric.label" class="bg-card px-3 py-2.5 sm:px-4 sm:py-3.5">
              <div class="flex items-center justify-between">
                <span class="text-[10px] sm:text-[11px] font-medium text-muted-foreground">{{ metric.label }}</span>
                <component :is="metric.icon" class="h-3.5 w-3.5 shrink-0" :class="metric.tone" />
              </div>
              <div class="mt-1 sm:mt-1.5 text-lg font-bold tracking-tight text-foreground sm:text-2xl font-mono">{{ metric.value }}</div>
              <div class="mt-0.5 text-[9px] sm:text-[10px] text-muted-foreground/70">{{ metric.hint }}</div>
            </div>
          </div>

          <!-- 紧凑处理进度条 -->
          <div class="relative mt-3.5 sm:mt-5 rounded-xl bg-muted/50 p-3 sm:p-4">
            <div class="mb-2 sm:mb-2.5 flex items-center justify-between gap-4">
              <div>
                <p class="text-[10.5px] sm:text-[11px] font-semibold text-foreground">处理进度</p>
                <p class="mt-0.5 text-[9.5px] sm:text-[10px] text-muted-foreground">{{ processedCount }} / {{ task.total || 0 }} 首</p>
              </div>
              <span class="text-xs sm:text-sm font-bold tabular-nums text-primary font-mono">{{ progressPercent }}%</span>
            </div>
            <Progress :model-value="progressPercent" class="h-1.5 sm:h-2 bg-background" />
          </div>
        </section>

        <!-- 正在处理卡片区 -->
        <section class="border-t border-border bg-[hsl(var(--surface-inset)/.58)] p-3.5 sm:p-5 lg:border-l lg:border-t-0 flex flex-col justify-between">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-xs font-bold text-foreground">正在处理</p>
              <p class="mt-0.5 text-[10px] text-muted-foreground">当前歌曲与处理步骤</p>
            </div>
            <Badge v-if="!task.current_track" variant="outline" class="text-[10px] py-0 px-2">空闲</Badge>
            <span v-else class="flex items-center gap-1.5 text-[10px] font-semibold text-primary"><RefreshCw class="h-3 w-3 animate-spin" />处理中</span>
          </div>

          <!-- 移动端自适应：小屏横向紧凑媒体条，大屏纵向展示 -->
          <div v-if="task.current_track" class="mt-3 sm:mt-4 flex items-center gap-3 rounded-xl border border-border/70 bg-card/60 p-2.5 sm:p-3 lg:mt-6 lg:block lg:border-0 lg:bg-transparent lg:p-0">
            <div class="relative h-14 w-14 sm:h-20 sm:w-20 shrink-0 overflow-hidden rounded-xl border border-border/80 shadow-md lg:h-auto lg:w-full lg:max-w-[210px] lg:aspect-square lg:rounded-2xl">
              <img
                :src="task.current_track.cover || 'https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=400&q=80'"
                class="h-full w-full object-cover pointer-events-none select-none"
                alt="歌曲封面"
              />
              <div class="absolute inset-0 bg-gradient-to-t from-black/20 via-transparent to-transparent" />
            </div>
            <div class="min-w-0 flex-1">
              <h4 class="truncate text-xs sm:text-sm font-bold text-foreground lg:mt-4">{{ task.current_track.title }}</h4>
              <p class="mt-0.5 truncate text-[11px] sm:text-xs text-muted-foreground">{{ task.current_track.artist }}</p>
              <p class="mt-1 flex items-center gap-1.5 truncate text-[10.5px] sm:text-[11px] font-medium leading-relaxed text-primary lg:mt-3">
                <span class="inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-primary animate-pulse" />
                <span class="truncate">{{ task.current_track.step || '正在整理歌曲信息…' }}</span>
              </p>
            </div>
          </div>

          <div v-else class="flex min-h-[120px] sm:min-h-[160px] flex-col items-center justify-center text-center lg:min-h-[220px]">
            <div class="grid h-10 w-10 sm:h-12 sm:w-12 place-items-center rounded-full border border-dashed border-border bg-card lg:h-14 lg:w-14"><Disc3 class="h-5 w-5 text-muted-foreground/60 lg:h-6 lg:w-6" /></div>
            <p class="mt-2.5 sm:mt-3 text-xs font-semibold text-foreground">等待新任务</p>
            <p class="mt-1 max-w-[220px] text-[10px] leading-relaxed text-muted-foreground">导入歌单后，这里会显示正在下载或入库的歌曲。</p>
          </div>
        </section>
      </div>
    </Card>

    <!-- 运行记录卡片 -->
    <Card class="overflow-hidden p-0">
      <div class="flex items-center justify-between border-b border-border px-3.5 py-3 sm:px-5">
        <div class="flex items-center gap-2.5 sm:gap-3">
          <span class="grid h-7 w-7 sm:h-8 sm:w-8 place-items-center rounded-lg bg-muted text-muted-foreground"><Terminal class="h-3.5 w-3.5 sm:h-4 sm:w-4" /></span>
          <div><p class="text-[11px] font-semibold text-foreground">运行记录</p><p class="mt-0.5 text-[9px] text-muted-foreground">用于排查下载和入库问题</p></div>
        </div>
        <span class="text-[10px] text-muted-foreground font-mono">{{ logs.length }} 条</span>
      </div>
      <div class="h-48 sm:h-56 overflow-y-auto bg-[hsl(var(--surface-inset)/.72)] p-3 sm:p-5 font-mono text-[10.5px] sm:text-[11px] leading-5 sm:leading-6">
        <div v-if="logs.length === 0" class="flex h-full flex-col items-center justify-center text-center text-muted-foreground"><Terminal class="h-5 w-5 opacity-60" /><p class="mt-2 text-xs">任务开始后会在这里显示记录</p></div>
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
