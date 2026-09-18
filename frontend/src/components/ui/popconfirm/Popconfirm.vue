<script setup lang="ts">
import { ref, watch } from 'vue';
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover';
import { PopoverArrow } from 'reka-ui';
import { Button } from '@/components/ui/button';
import { AlertTriangle, AlertCircle, Loader2 } from 'lucide-vue-next';
import { cn } from '@/lib/utils';

interface Props {
  title: string;
  description?: string;
  detail?: string;
  confirmText?: string;
  cancelText?: string;
  danger?: boolean;
  loading?: boolean;
  side?: 'top' | 'right' | 'bottom' | 'left';
  align?: 'start' | 'center' | 'end';
  widthClass?: string;
  open?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  danger: true,
  side: 'top',
  align: 'end',
  widthClass: 'w-[min(21rem,calc(100vw-1.5rem))]'
});

const emit = defineEmits<{
  (e: 'confirm'): void;
  (e: 'cancel'): void;
  (e: 'update:open', value: boolean): void;
}>();

const isOpen = ref(false);

watch(
  () => props.open,
  (val) => {
    if (val !== undefined) {
      isOpen.value = val;
    }
  }
);

function onOpenChange(val: boolean) {
  isOpen.value = val;
  emit('update:open', val);
  if (!val) {
    emit('cancel');
  }
}

function handleConfirm() {
  emit('confirm');
}

function handleCancel() {
  isOpen.value = false;
  emit('update:open', false);
  emit('cancel');
}

defineExpose({
  close: () => {
    isOpen.value = false;
    emit('update:open', false);
  }
});
</script>

<template>
  <Popover :open="isOpen" @update:open="onOpenChange">
    <PopoverTrigger as-child>
      <slot />
    </PopoverTrigger>

    <PopoverContent
      :side="props.side"
      :align="props.align"
      :side-offset="8"
      :collision-padding="12"
      :class="cn(
        'p-4 bg-card/95 border border-border/90 backdrop-blur-2xl shadow-[0_24px_64px_-12px_hsl(var(--shadow-color)/.65),0_0_0_1px_rgba(255,255,255,0.06)] rounded-2xl space-y-3 z-[85] text-card-foreground',
        props.widthClass
      )"
    >
      <div class="flex items-start gap-3">
        <!-- 警示图标微章 -->
        <div
          class="w-8 h-8 rounded-xl flex items-center justify-center shrink-0 shadow-sm transition-transform"
          :class="danger
            ? 'bg-destructive/15 text-destructive ring-1 ring-destructive/30 shadow-[0_0_12px_hsl(var(--destructive)/0.2)]'
            : 'bg-warning/15 text-warning ring-1 ring-warning/30 shadow-[0_0_12px_hsl(var(--warning)/0.2)]'"
        >
          <AlertCircle v-if="danger" class="w-4 h-4 stroke-[2.2]" />
          <AlertTriangle v-else class="w-4 h-4 stroke-[2.2]" />
        </div>

        <div class="space-y-1 overflow-hidden flex-1 min-w-0">
          <h4 class="text-[13px] font-semibold text-foreground tracking-tight leading-snug break-words">
            {{ title }}
          </h4>
          <p v-if="description" class="text-xs text-muted-foreground leading-relaxed break-words">
            {{ description }}
          </p>
          <div
            v-if="detail"
            class="mt-1.5 rounded-lg bg-surface-inset/85 border border-border/70 p-2 text-[11px] text-muted-foreground/90 font-mono break-all leading-relaxed"
          >
            {{ detail }}
          </div>
        </div>
      </div>

      <slot name="extra" />

      <!-- 操作按钮栏 -->
      <div class="flex justify-end items-center gap-2 pt-2.5 border-t border-border/70">
        <Button
          size="sm"
          variant="ghost"
          @click="handleCancel"
          :disabled="loading"
          class="h-8 px-3 text-xs rounded-xl text-muted-foreground hover:text-foreground hover:bg-muted/70 active:scale-95 transition-all font-medium"
        >
          {{ cancelText || '取消' }}
        </Button>
        <Button
          size="sm"
          :variant="danger ? 'destructive' : 'brand'"
          @click="handleConfirm"
          :disabled="loading"
          class="h-8 px-3.5 text-xs rounded-xl flex items-center gap-1.5 shadow-sm font-semibold active:scale-95 transition-all"
        >
          <Loader2 v-if="loading" class="w-3.5 h-3.5 animate-spin" />
          <span>{{ loading ? '处理中...' : (confirmText || '确定') }}</span>
        </Button>
      </div>

      <!-- 精致的气泡指示小箭头 -->
      <PopoverArrow class="fill-card drop-shadow-[0_1px_0_hsl(var(--border))]" :width="11" :height="5" />
    </PopoverContent>
  </Popover>
</template>
