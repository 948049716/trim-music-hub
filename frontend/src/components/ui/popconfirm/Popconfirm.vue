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
  widthClass: 'w-[min(20rem,calc(100vw-2rem))]'
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
      :side-offset="6"
      :collision-padding="12"
      :class="cn(
        'p-3.5 bg-card/95 border border-border/90 backdrop-blur-2xl shadow-[0_20px_48px_-8px_rgba(0,0,0,0.75),0_0_0_1px_rgba(255,255,255,0.06)] rounded-2xl space-y-2.5 z-[80] text-card-foreground max-w-[calc(100vw-1.5rem)]',
        props.widthClass || 'w-80'
      )"
    >
      <div class="flex items-start gap-2.5">
        <div
          class="w-7 h-7 rounded-lg flex items-center justify-center shrink-0 mt-0.5"
          :class="danger ? 'bg-destructive/15 text-destructive border border-destructive/25' : 'bg-amber-500/15 text-amber-500 border border-amber-500/25'"
        >
          <AlertTriangle class="w-3.5 h-3.5" />
        </div>
        <div class="space-y-1 overflow-hidden flex-1 min-w-0">
          <h4 class="text-xs sm:text-[13px] font-bold text-foreground tracking-tight leading-snug break-words">
            {{ title }}
          </h4>
          <p v-if="description" class="text-[11px] sm:text-xs text-muted-foreground leading-relaxed break-words">
            {{ description }}
          </p>
          <div v-if="detail" class="rounded-md bg-muted/60 border border-border/70 px-2 py-1 text-[10px] sm:text-[10.5px] text-muted-foreground/90 font-mono break-all leading-tight">
            {{ detail }}
          </div>
        </div>
      </div>

      <slot name="extra" />

      <div class="flex justify-end items-center gap-2 pt-2 border-t border-border/70">
        <Button
          size="sm"
          variant="ghost"
          @click="handleCancel"
          :disabled="loading"
          class="h-7 px-2.5 text-[11.5px] rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted/60"
        >
          {{ cancelText || '取消' }}
        </Button>
        <Button
          size="sm"
          :variant="danger ? 'destructive' : 'brand'"
          @click="handleConfirm"
          :disabled="loading"
          class="h-7 px-3 text-[11.5px] rounded-lg flex items-center gap-1.5 shadow-sm font-semibold active:scale-95 transition-transform"
        >
          <Loader2 v-if="loading" class="w-3 h-3 animate-spin" />
          <span>{{ loading ? '处理中...' : (confirmText || '确定') }}</span>
        </Button>
      </div>
    </PopoverContent>
  </Popover>
</template>
