<script setup lang="ts">
import { Loader2 } from 'lucide-vue-next'

withDefaults(
  defineProps<{
    title?: string
    description?: string
  }>(),
  {
    title: '正在加载…',
    description: '',
  }
)
</script>

<template>
  <div class="flex min-h-[240px] flex-col items-center justify-center p-6 text-center select-none">
    <div class="relative grid h-12 w-12 place-items-center rounded-2xl bg-primary/10 text-primary">
      <Loader2 class="h-6 w-6 animate-spin" />
    </div>
    <h3 class="mt-3.5 text-xs sm:text-sm font-semibold tracking-tight text-foreground">
      {{ title }}
    </h3>
    <p v-if="description" class="mt-1 text-xs text-muted-foreground">
      {{ description }}
    </p>
  </div>
</template>
