<script setup lang="ts">
import type { Component } from 'vue'
import { Inbox } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'

const props = withDefaults(
  defineProps<{
    icon?: Component
    title?: string
    description?: string
    actionText?: string
  }>(),
  {
    icon: Inbox,
    title: '暂无内容',
    description: '',
    actionText: '',
  }
)

const emit = defineEmits<{
  (e: 'action'): void
}>()
</script>

<template>
  <div class="flex min-h-[260px] flex-col items-center justify-center p-6 text-center select-none">
    <div class="grid h-12 w-12 sm:h-14 sm:w-14 place-items-center rounded-2xl border border-border/80 bg-muted/60 text-muted-foreground shadow-sm">
      <component :is="props.icon" class="h-6 w-6 opacity-75" />
    </div>
    <h3 class="mt-3.5 text-sm sm:text-base font-bold tracking-tight text-foreground">
      {{ props.title }}
    </h3>
    <p v-if="props.description" class="mt-1.5 max-w-sm text-xs sm:text-sm text-muted-foreground leading-relaxed">
      {{ props.description }}
    </p>
    <div v-if="$slots.action || props.actionText" class="mt-5">
      <slot name="action">
        <Button size="sm" variant="outline" @click="emit('action')">
          {{ props.actionText }}
        </Button>
      </slot>
    </div>
  </div>
</template>
