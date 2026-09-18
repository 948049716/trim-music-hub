<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue';
import { Loader2, ArrowDown } from 'lucide-vue-next';

interface Props {
  refreshing?: boolean;
  disabled?: boolean;
  threshold?: number;
  maxPull?: number;
}

const props = withDefaults(defineProps<Props>(), {
  refreshing: false,
  disabled: false,
  threshold: 64,
  maxPull: 110,
});

const emit = defineEmits<{
  (e: 'refresh'): void;
}>();

const containerRef = ref<HTMLElement | null>(null);
const pullDistance = ref(0);
const isTouching = ref(false);
let startY = 0;
let startX = 0;
let isCandidate = false;

// 阻尼拉伸计算：拉得越深，阻力越大
const indicatorOffset = computed(() => {
  if (props.refreshing) return 48;
  return pullDistance.value;
});

const pullProgress = computed(() => {
  return Math.min(1, pullDistance.value / props.threshold);
});

const isReadyToRelease = computed(() => {
  return pullDistance.value >= props.threshold;
});

function onTouchStart(e: TouchEvent) {
  if (props.disabled || props.refreshing) return;
  if (!containerRef.value) return;

  // 只有当内部滚动条已经在最顶部（scrollTop === 0）时，才触发下拉刷新候选
  if (containerRef.value.scrollTop <= 0) {
    startY = e.touches[0].clientY;
    startX = e.touches[0].clientX;
    isCandidate = true;
  } else {
    isCandidate = false;
  }
}

function onTouchMove(e: TouchEvent) {
  if (!isCandidate || props.disabled || props.refreshing || !containerRef.value) return;

  const currentY = e.touches[0].clientY;
  const currentX = e.touches[0].clientX;
  const diffY = currentY - startY;
  const diffX = Math.abs(currentX - startX);

  // 若手势向上滑动（说明用户是在向下滚动浏览列表），立即彻底放弃下拉刷新候选，0延迟释放给浏览器原生滚动
  if (diffY <= 0) {
    isCandidate = false;
    isTouching.value = false;
    pullDistance.value = 0;
    return;
  }

  // 只有当内部滚动条处于最顶端且明确向下拖拽超过阈值（垂直位移大于横向偏移且大于 10px）时才拦截
  if (containerRef.value.scrollTop <= 0 && diffY > diffX * 1.5 && diffY > 10) {
    isTouching.value = true;
    const damping = 0.48;
    const distance = Math.min(props.maxPull, (diffY - 10) * damping);
    pullDistance.value = distance;

    // 仅在明确接管下拉刷新拖拽位移时拦截浏览器原生外溢
    if (e.cancelable) {
      e.preventDefault();
    }
  } else if (containerRef.value.scrollTop > 0) {
    // 滚动条已离开顶部，直接退出
    isCandidate = false;
    isTouching.value = false;
    pullDistance.value = 0;
  }
}
function onTouchEnd() {
  if (!isTouching.value) {
    isCandidate = false;
    return;
  }

  isTouching.value = false;
  isCandidate = false;

  if (pullDistance.value >= props.threshold && !props.refreshing) {
    emit('refresh');
  }

  // 松手归位过渡
  pullDistance.value = 0;
}

function onTouchCancel() {
  isTouching.value = false;
  isCandidate = false;
  pullDistance.value = 0;
}

onUnmounted(() => {
  pullDistance.value = 0;
});

defineExpose({
  scrollToTop: (options?: ScrollToOptions) => {
    containerRef.value?.scrollTo({ top: 0, ...options });
  },
  getScrollTop: () => containerRef.value?.scrollTop || 0,
});
</script>

<template>
  <div
    ref="containerRef"
    class="pull-refresh-container relative flex-1 min-h-0 w-full overflow-y-auto overflow-x-hidden select-text overscroll-contain"
    @touchstart="onTouchStart"
    @touchmove="onTouchMove"
    @touchend="onTouchEnd"
    @touchcancel="onTouchCancel"
  >
    <!-- 下拉刷新视觉胶囊指示器 -->
    <div
      class="pull-refresh-indicator absolute left-0 right-0 top-0 z-30 flex justify-center pointer-events-none transition-transform"
      :style="{
        transform: `translate3d(0, ${indicatorOffset - 40}px, 0)`,
        transitionDuration: isTouching ? '0ms' : '280ms',
        opacity: indicatorOffset > 8 || props.refreshing ? 1 : 0
      }"
    >
      <div
        class="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-border/80 bg-card/90 backdrop-blur-md shadow-lg text-xs font-medium text-foreground transition-all"
        :class="{
          'border-primary/40 text-primary': isReadyToRelease || props.refreshing
        }"
      >
        <Loader2 v-if="props.refreshing" class="w-3.5 h-3.5 animate-spin text-primary" />
        <ArrowDown
          v-else
          class="w-3.5 h-3.5 transition-transform duration-200"
          :class="{
            'rotate-180 text-primary': isReadyToRelease,
            'text-muted-foreground': !isReadyToRelease
          }"
          :style="{
            opacity: Math.max(0.4, pullProgress)
          }"
        />
        <span class="text-[11px]">
          {{ props.refreshing ? '正在刷新…' : isReadyToRelease ? '释放立即刷新' : '下拉刷新列表' }}
        </span>
      </div>
    </div>

    <!-- 列表实际内容区域（下拉时带轻微弹性位移） -->
    <div
      class="pull-refresh-content"
      :class="{ 'transition-transform duration-200': !isTouching }"
      :style="pullDistance > 0 || props.refreshing ? {
        transform: `translate3d(0, ${indicatorOffset * 0.35}px, 0)`
      } : undefined">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.pull-refresh-container {
  touch-action: pan-y;
  overscroll-behavior-y: contain;
  -webkit-overflow-scrolling: touch;
}
</style>
