<script setup lang="ts" generic="T extends string | number">
import { ref, watch, type HTMLAttributes } from 'vue';
import { cn } from '@/lib/utils';
import { useSpringInertia } from '@/composables/useSpringInertia';

export interface SpringTabItem<V = any> {
  value: V;
  label: string;
  icon?: any;
  badge?: string | number;
  badgeClass?: string;
  disabled?: boolean;
}

const props = withDefaults(
  defineProps<{
    modelValue: T;
    items: SpringTabItem<T>[];
    size?: 'sm' | 'default' | 'lg';
    variant?: 'default' | 'primary';
    class?: HTMLAttributes['class'];
    pillClass?: string;
  }>(),
  {
    size: 'sm',
    variant: 'default',
  }
);

const emit = defineEmits<{
  (e: 'update:modelValue', val: T): void;
}>();

const containerRef = ref<HTMLElement | null>(null);
const sliderRef = ref<HTMLElement | null>(null);
const itemRefs = ref<HTMLElement[]>([]);

function setItemRef(el: any, idx: number) {
  if (el) itemRefs.value[idx] = el as HTMLElement;
}

const localValue = ref<T>(props.modelValue);

watch(() => props.modelValue, (val) => {
  localValue.value = val;
});

const { isReady, updateIndicator } = useSpringInertia(
  containerRef,
  sliderRef,
  itemRefs,
  {
    getActiveIndex: () => props.items.findIndex(item => item.value === localValue.value),
  }
);

let internalTargetVal: T | null = null;

function selectTab(val: T, newIdx: number) {
  if (val === localValue.value) return;
  const oldIdx = props.items.findIndex(item => item.value === localValue.value);
  const steps = Math.abs(newIdx - (oldIdx !== -1 ? oldIdx : newIdx)) || 1;
  internalTargetVal = val;
  localValue.value = val;
  updateIndicator(false, steps, newIdx);
  emit('update:modelValue', val);
}

watch(() => props.modelValue, (newVal, oldVal) => {
  if (internalTargetVal === newVal) {
    internalTargetVal = null;
    return;
  }
  internalTargetVal = null;
  const oldIdx = oldVal !== undefined ? props.items.findIndex(item => item.value === oldVal) : -1;
  const newIdx = props.items.findIndex(item => item.value === newVal);
  if (newIdx !== -1) {
    const steps = Math.abs(newIdx - (oldIdx !== -1 ? oldIdx : newIdx)) || 1;
    updateIndicator(false, steps, newIdx);
  }
});
</script>

<template>
  <div
    ref="containerRef"
    role="tablist"
    :class="cn(
      'spring-tabs-container relative inline-flex items-center rounded-xl border border-border/80 bg-background/80 p-1 isolate select-none',
      props.class
    )"
  >
    <!-- 物理弹簧滑块指示底座 (硬件加速平滑穿梭) -->
    <div
      ref="sliderRef"
      class="spring-tabs-slider pointer-events-none absolute top-1 bottom-1 left-0 z-0 will-change-transform"
      :class="{ 'opacity-100': isReady, 'opacity-0': !isReady }"
      aria-hidden="true"
    >
      <div
        :class="cn(
          'spring-tabs-pill w-[calc(100%-6px)] mx-[3px] h-full rounded-lg transition-colors',
          variant === 'primary'
            ? 'bg-primary/12 border border-primary/25 shadow-[0_0_12px_-2px_hsl(var(--primary)/0.2)]'
            : 'bg-card text-foreground shadow-sm ring-1 ring-border/60',
          props.pillClass
        )"
      />
    </div>

    <!-- 标签项列表 -->
    <button
      v-for="(item, idx) in items"
      :key="String(item.value)"
      :ref="(el) => setItemRef(el, idx)"
      type="button"
      role="tab"
      :disabled="item.disabled"
      :aria-selected="localValue === item.value"
      :tabindex="localValue === item.value ? 0 : -1"
      :class="cn(
        'spring-tabs-item relative z-10 flex-1 flex items-center justify-center whitespace-nowrap gap-1.5 rounded-lg font-semibold transition-colors duration-150 cursor-pointer disabled:cursor-not-allowed disabled:opacity-40 outline-none focus-visible:ring-2 focus-visible:ring-ring/60',
        size === 'sm' && 'px-3 py-1.5 text-xs',
        size === 'default' && 'px-3.5 py-1.5 text-xs sm:text-sm sm:px-4 sm:py-2',
        size === 'lg' && 'px-4 py-2 text-sm sm:text-base sm:px-5 sm:py-2.5',
        localValue === item.value
          ? (variant === 'primary' ? 'text-primary' : 'text-foreground')
          : 'text-muted-foreground hover:text-foreground'
      )"
      @click="selectTab(item.value, idx)"
    >
      <slot name="item" :item="item" :active="localValue === item.value">
        <component
          :is="item.icon"
          v-if="item.icon"
          :class="cn(
            'shrink-0 transition-transform duration-150',
            size === 'sm' ? 'w-3.5 h-3.5' : 'w-4 h-4',
            localValue === item.value && 'scale-105'
          )"
        />
        <span>{{ item.label }}</span>
        <span
          v-if="item.badge !== undefined && item.badge !== null"
          :class="cn(
            'font-mono rounded-full px-1.5 py-0.2 text-[10px] leading-tight shrink-0 transition-colors',
            item.badgeClass || (localValue === item.value ? 'bg-muted text-foreground' : 'bg-muted/60 text-muted-foreground')
          )"
        >
          {{ item.badge }}
        </span>
      </slot>
    </button>
  </div>
</template>

<style scoped>
.spring-tabs-slider {
  transition: opacity 150ms ease;
  transform-origin: center center;
  -webkit-backface-visibility: hidden;
  backface-visibility: hidden;
}
</style>
