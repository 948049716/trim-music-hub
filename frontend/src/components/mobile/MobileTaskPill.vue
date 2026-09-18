<script setup lang="ts">
import { computed } from 'vue';
import type { TaskState } from '../../types';
import { Disc3, ChevronRight } from 'lucide-vue-next';

const props = defineProps<{
  task: TaskState;
  visible: boolean;
}>();

const emit = defineEmits<{
  (e: 'click'): void;
}>();

const isRunning = computed(() => ['downloading', 'parsing', 'finalizing'].includes(props.task.status));

const processedCount = computed(() =>
  (props.task.reused_count || 0) + (props.task.downloaded_count || 0) + (props.task.failed_count || 0)
);

const progressPercent = computed(() => {
  if (!props.task.total) return 0;
  return Math.min(100, Math.round((processedCount.value / props.task.total) * 100));
});

const currentTitle = computed(() => {
  if (props.task.current_track?.title) {
    return props.task.current_track.title;
  }
  return props.task.playlist_name || '正在同步歌单...';
});

const currentSubtitle = computed(() => {
  if (props.task.current_track?.artist) {
    return `${props.task.current_track.artist} · ${props.task.current_track.step || '处理中'}`;
  }
  return `已处理 ${processedCount.value} / ${props.task.total || 0} 首`;
});

const currentCover = computed(() => {
  return props.task.current_track?.cover || '';
});
</script>

<template>
  <Transition name="task-pill-slide">
    <aside
      v-if="visible && isRunning"
      class="fixed left-1/2 z-40 flex w-[calc(100%-1.25rem)] max-w-lg -translate-x-1/2 cursor-pointer items-center justify-between gap-3 rounded-2xl border border-primary/30 bg-card/90 px-3 py-2 shadow-2xl backdrop-blur-2xl transition-all active:scale-[0.98] lg:hidden"
      :style="{ bottom: 'calc(4.65rem + env(safe-area-inset-bottom, 0px))' }"
      role="button"
      aria-label="查看正在进行的同步任务"
      @click="emit('click')"
    >
      <div class="flex min-w-0 flex-1 items-center gap-2.5">
        <!-- 唱片封面 -->
        <div class="relative grid h-10 w-10 shrink-0 place-items-center overflow-hidden rounded-xl border border-border/80 bg-muted shadow-sm">
          <img
            v-if="currentCover"
            :src="currentCover"
            alt="封面"
            class="h-full w-full object-cover"
            loading="lazy"
          />
          <Disc3 v-else class="h-5 w-5 animate-spin-slow text-primary" />
          <div class="absolute inset-0 bg-black/10" />
        </div>

        <!-- 标题与状态 -->
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-1.5">
            <span class="flex h-1.5 w-1.5 animate-ping rounded-full bg-primary" />
            <h4 class="truncate text-xs font-bold text-foreground">
              {{ currentTitle }}
            </h4>
          </div>
          <p class="mt-0.5 truncate text-[10px] text-muted-foreground">
            {{ currentSubtitle }}
          </p>
        </div>
      </div>

      <!-- 进度与直达 -->
      <div class="flex shrink-0 items-center gap-2">
        <div class="flex flex-col items-end">
          <span class="text-[11px] font-extrabold tabular-nums text-primary">
            {{ progressPercent }}%
          </span>
          <span class="text-[9px] text-muted-foreground">
            {{ processedCount }}/{{ task.total || 0 }}
          </span>
        </div>
        <div class="grid h-7 w-7 place-items-center rounded-full bg-primary/10 text-primary">
          <ChevronRight class="h-4 w-4" />
        </div>
      </div>
    </aside>
  </Transition>
</template>

<style scoped>
.task-pill-slide-enter-active,
.task-pill-slide-leave-active {
  transition: opacity 220ms cubic-bezier(0.16, 1, 0.3, 1), transform 220ms cubic-bezier(0.16, 1, 0.3, 1);
}
.task-pill-slide-enter-from,
.task-pill-slide-leave-to {
  opacity: 0;
  transform: translate(-50%, 12px) scale(0.96);
}
</style>
