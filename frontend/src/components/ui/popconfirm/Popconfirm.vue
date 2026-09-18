<script setup lang="ts">
import { ref, watch } from 'vue';
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover';
import { Button } from '@/components/ui/button';
import { AlertTriangle, Loader2 } from 'lucide-vue-next';
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
  widthClass: 'w-72'
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
      :class="cn(
        'p-4 bg-popover border border-border backdrop-blur-2xl shadow-[0_22px_64px_hsl(var(--shadow-color)/.25)] rounded-2xl space-y-3 z-50 text-popover-foreground max-w-[calc(100vw-1.5rem)]',
        props.widthClass || 'w-80'
      )"
    >
      <div class="flex items-start gap-3">
        <div
          class="w-8 h-8 rounded-xl flex items-center justify-center shrink-0 mt-0.5"
          :class="danger ? 'bg-rose-500/15 text-rose-400 border border-rose-500/25' : 'bg-amber-500/15 text-amber-400 border border-amber-500/25'"
        >
          <AlertTriangle class="w-4 h-4" />
        </div>
        <div class="space-y-1.5 overflow-hidden flex-1 min-w-0">
          <h4 class="text-xs sm:text-sm font-semibold text-foreground tracking-tight leading-snug break-words">
            {{ title }}
          </h4>
          <p v-if="description" class="text-xs text-muted-foreground leading-relaxed break-words">
            {{ description }}
          </p>
          <div v-if="detail" class="rounded-lg bg-muted border border-border px-2.5 py-1.5 text-[11px] text-muted-foreground font-mono break-all leading-tight">
            {{ detail }}
          </div>
        </div>
      </div>

      <slot name="extra" />

      <div class="flex justify-end items-center gap-2 pt-2.5 border-t border-border">
        <Button
          size="sm"
          variant="ghost"
          @click="handleCancel"
          :disabled="loading"
          class="h-7 px-3 text-xs rounded-lg text-muted-foreground hover:text-foreground"
        >
          {{ cancelText || '取消' }}
        </Button>
        <Button
          size="sm"
          :variant="danger ? 'destructive' : 'brand'"
          @click="handleConfirm"
          :disabled="loading"
          class="h-7 px-3 text-xs rounded-lg flex items-center gap-1.5 shadow-sm font-medium"
        >
          <Loader2 v-if="loading" class="w-3.5 h-3.5 animate-spin" />
          <span>{{ loading ? '处理中...' : (confirmText || '确定') }}</span>
        </Button>
      </div>
    </PopoverContent>
  </Popover>
</template>

