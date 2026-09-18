<script setup lang="ts">
import { toasts } from '../composables/useToast';
import { CheckCircle2, AlertCircle, Info, XCircle } from 'lucide-vue-next';
</script>
<template>
  <div class="pointer-events-none fixed inset-x-3 bottom-[calc(5.75rem+env(safe-area-inset-bottom))] z-[80] flex flex-col items-end gap-2 sm:inset-x-auto sm:bottom-6 sm:right-6 sm:w-full sm:max-w-sm">
    <transition-group enter-active-class="transform ease-out duration-200 transition" enter-from-class="translate-y-3 opacity-0 scale-95" enter-to-class="translate-y-0 opacity-100 scale-100" leave-active-class="transition ease-in duration-150" leave-from-class="opacity-100" leave-to-class="opacity-0 scale-95">
      <div v-for="t in toasts" :key="t.id" class="pointer-events-auto flex w-full items-start gap-3 rounded-xl border border-border/85 bg-popover/95 backdrop-blur-xl px-4 py-3 text-xs sm:text-sm font-medium text-popover-foreground shadow-[0_18px_48px_hsl(var(--shadow-color)/.22)]">
        <CheckCircle2 v-if="t.type === 'success'" class="mt-0.5 h-4 w-4 shrink-0 text-success" />
        <XCircle v-else-if="t.type === 'error'" class="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
        <AlertCircle v-else-if="t.type === 'warning'" class="mt-0.5 h-4 w-4 shrink-0 text-warning" />
        <Info v-else class="mt-0.5 h-4 w-4 shrink-0 text-primary" />
        <span class="flex-1 break-words leading-snug">{{ t.message }}</span>
      </div>
    </transition-group>
  </div>
</template>
