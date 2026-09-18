<script setup lang="ts">
import { Button } from '@/components/ui/button';
import { Popconfirm } from '@/components/ui/popconfirm';
import { Loader2, Trash2 } from 'lucide-vue-next';

interface Props {
  show: boolean;
  count: number;
  unit?: string;
  sizeText?: string;
  cancelText?: string;
  actionText?: string;
  confirmTitle?: string;
  confirmDesc?: string;
  confirmDetail?: string;
  confirmBtnText?: string;
  danger?: boolean;
  loading?: boolean;
  popconfirmWidthClass?: string;
}

const props = withDefaults(defineProps<Props>(), {
  unit: '项',
  cancelText: '取消',
  actionText: '删除',
  danger: true,
  loading: false,
  popconfirmWidthClass: 'w-80 sm:w-96',
});

const emit = defineEmits<{
  (e: 'cancel'): void;
  (e: 'confirm'): void;
}>();
</script>

<template>
  <Transition
    enter-active-class="transition-all duration-200 ease-out"
    enter-from-class="opacity-0 translate-y-3 scale-95"
    enter-to-class="opacity-100 translate-y-0 scale-100"
    leave-active-class="transition-all duration-150 ease-in"
    leave-from-class="opacity-100 translate-y-0 scale-100"
    leave-to-class="opacity-0 translate-y-2 scale-95"
  >
    <div
      v-if="show && count > 0"
      class="batch-action-bar-island fixed z-[55] left-3 right-3 sm:left-1/2 sm:right-auto sm:-translate-x-1/2 flex items-center justify-between gap-3 px-3.5 py-2.5 rounded-2xl border border-border/80 bg-card/95 backdrop-blur-2xl shadow-[0_16px_42px_hsl(var(--shadow-color)/.28)]"
      :style="{ bottom: 'calc(4.35rem + env(safe-area-inset-bottom, 0px))' }"
    >
      <!-- 左侧：选择状态与数量提示 -->
      <div class="flex items-center gap-2 min-w-0">
        <span
          class="h-2 w-2 shrink-0 rounded-full animate-pulse"
          :class="danger ? 'bg-destructive shadow-[0_0_8px_rgba(239,68,68,0.75)]' : 'bg-primary shadow-[0_0_8px_rgba(59,130,246,0.75)]'"
        />
        <div class="flex items-center gap-1 truncate text-xs">
          <span class="text-muted-foreground">已选</span>
          <strong class="font-bold tabular-nums text-foreground font-mono" :class="danger ? 'text-rose-500 dark:text-rose-400' : 'text-primary'">
            {{ count }}
          </strong>
          <span class="text-muted-foreground">{{ unit }}</span>
          <span v-if="sizeText" class="ml-1 rounded bg-muted/80 px-1.5 py-0.5 font-mono text-[10.5px] text-muted-foreground">
            {{ sizeText }}
          </span>
        </div>
      </div>

      <!-- 右侧：取消与确认操作 -->
      <div class="flex items-center gap-1.5 shrink-0">
        <Button
          variant="ghost"
          size="sm"
          class="h-8 px-2.5 text-xs text-muted-foreground hover:text-foreground active:scale-95"
          :disabled="loading"
          @click="emit('cancel')"
        >
          {{ cancelText }}
        </Button>

        <Popconfirm
          :title="confirmTitle || `确认${actionText}选中的 ${count} ${unit}？`"
          :description="confirmDesc"
          :detail="confirmDetail"
          :confirm-text="confirmBtnText || actionText"
          :danger="danger"
          :loading="loading"
          side="top"
          align="end"
          :width-class="popconfirmWidthClass"
          @confirm="emit('confirm')"
        >
          <template #extra v-if="$slots.extra">
            <slot name="extra" />
          </template>

          <Button
            size="sm"
            :variant="danger ? 'destructive' : 'brand'"
            :disabled="loading"
            class="h-8 px-3 text-xs font-semibold gap-1.5 rounded-xl active:scale-95 transition-transform shadow-sm"
          >
            <Loader2 v-if="loading" class="h-3.5 w-3.5 animate-spin" />
            <Trash2 v-else-if="danger" class="h-3.5 w-3.5" />
            <span>{{ actionText }} {{ count }} {{ unit }}</span>
          </Button>
        </Popconfirm>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
@media (min-width: 1024px) {
  .batch-action-bar-island {
    bottom: 1.5rem !important;
    min-width: 360px;
    max-width: 480px;
  }
}
</style>
