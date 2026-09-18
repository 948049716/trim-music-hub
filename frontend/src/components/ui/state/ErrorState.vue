<script setup lang="ts">
import { AlertTriangle, RefreshCw } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'

withDefaults(
  defineProps<{
    title?: string
    description?: string
    retryText?: string
  }>(),
  {
    title: '加载出错',
    description: '请求未能成功完成，请稍后重试。',
    retryText: '重试',
  }
)

const emit = defineEmits<{
  (e: 'retry'): void
}>()
</script>

<template>
  <div class="flex min-h-[260px] flex-col items-center justify-center p-6 text-center select-none">
    <div class="grid h-12 w-12 sm:h-14 sm:w-14 place-items-center rounded-2xl border border-destructive/25 bg-destructive/10 text-destructive shadow-sm">
      <AlertTriangle class="h-6 w-6" />
    </div>
    <h3 class="mt-3.5 text-sm sm:text-base font-bold tracking-tight text-foreground">
      {{ title }}
    </h3>
    <p v-if="description" class="mt-1.5 max-w-sm text-xs sm:text-sm text-muted-foreground leading-relaxed">
      {{ description }}
    </p>
    <div v-if="$slots.action || retryText" class="mt-5">
      <slot name="action">
        <Button size="sm" variant="outline" class="gap-1.5" @click="emit('retry')">
          <RefreshCw class="h-3.5 w-3.5" />
          {{ retryText }}
        </Button>
      </slot>
    </div>
  </div>
</template>
