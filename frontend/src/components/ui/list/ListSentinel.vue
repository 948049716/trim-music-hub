<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue';
import { Loader2 } from 'lucide-vue-next';

const props = withDefaults(
  defineProps<{
    loading?: boolean;
    hasMore?: boolean;
    total?: number;
    unit?: string;
    loadingText?: string;
    allLoadedText?: string;
    rootRef?: HTMLElement | null;
    rootMargin?: string;
  }>(),
  {
    loading: false,
    hasMore: false,
    total: 0,
    unit: '项',
    loadingText: '正在加载更多…',
    allLoadedText: '',
    rootRef: null,
    rootMargin: '160px',
  }
);

const emit = defineEmits<{
  (e: 'load-more'): void;
}>();

const sentinelEl = ref<HTMLElement | null>(null);
let observer: IntersectionObserver | null = null;

function setupObserver() {
  cleanupObserver();
  if (!sentinelEl.value) return;

  observer = new IntersectionObserver(
    (entries) => {
      const entry = entries[0];
      if (entry && entry.isIntersecting && props.hasMore && !props.loading) {
        emit('load-more');
      }
    },
    {
      root: props.rootRef || null,
      rootMargin: props.rootMargin,
    }
  );

  observer.observe(sentinelEl.value);
}

function cleanupObserver() {
  if (observer) {
    observer.disconnect();
    observer = null;
  }
}

watch(
  () => [props.rootRef, props.hasMore, props.loading],
  () => {
    // 若状态变化，微任务后重新挂载观察
    setupObserver();
  },
  { flush: 'post' }
);

onMounted(() => {
  setupObserver();
});

onUnmounted(() => {
  cleanupObserver();
});
</script>

<template>
  <div ref="sentinelEl" class="py-3 text-center select-none shrink-0" aria-live="polite">
    <!-- 加载中状态 -->
    <div v-if="loading" class="flex items-center justify-center gap-2 py-2 text-xs text-muted-foreground">
      <Loader2 class="h-4 w-4 animate-spin text-primary" />
      <span>{{ loadingText }}</span>
    </div>

    <!-- 已全部加载完成状态 -->
    <div
      v-else-if="!hasMore && total > 0"
      class="flex items-center justify-center gap-3 py-2 text-[11px] text-muted-foreground/75"
    >
      <span class="h-px w-8 sm:w-12 bg-border/80" />
      <span>{{ allLoadedText || `已显示全部 ${total} ${unit}` }}</span>
      <span class="h-px w-8 sm:w-12 bg-border/80" />
    </div>
  </div>
</template>
