<script setup lang="ts">
import { toasts } from '../composables/useToast';
import { CheckCircle2, AlertCircle, Info, XCircle } from 'lucide-vue-next';
</script>

<template>
  <div class="fixed bottom-6 right-6 z-50 flex flex-col gap-2.5 max-w-sm w-full pointer-events-none px-4">
    <transition-group
      enter-active-class="transform ease-out duration-300 transition"
      enter-from-class="translate-y-4 opacity-0 scale-95"
      enter-to-class="translate-y-0 opacity-100 scale-100"
      leave-active-class="transition ease-in duration-200"
      leave-from-class="opacity-100 scale-100"
      leave-to-class="opacity-0 scale-90"
    >
      <div
        v-for="t in toasts"
        :key="t.id"
        class="pointer-events-auto flex items-center gap-3 px-4 py-3 rounded-xl shadow-2xl backdrop-blur-xl border text-sm font-medium transition-all"
        :class="{
          'bg-emerald-950/80 border-emerald-500/30 text-emerald-200': t.type === 'success',
          'bg-rose-950/80 border-rose-500/30 text-rose-200': t.type === 'error',
          'bg-amber-950/80 border-amber-500/30 text-amber-200': t.type === 'warning',
          'bg-slate-900/85 border-slate-700/50 text-slate-200': t.type === 'info'
        }"
      >
        <CheckCircle2 v-if="t.type === 'success'" class="w-4 h-4 text-emerald-400 shrink-0" />
        <XCircle v-else-if="t.type === 'error'" class="w-4 h-4 text-rose-400 shrink-0" />
        <AlertCircle v-else-if="t.type === 'warning'" class="w-4 h-4 text-amber-400 shrink-0" />
        <Info v-else class="w-4 h-4 text-sky-400 shrink-0" />
        <span class="flex-1 leading-snug break-words">{{ t.message }}</span>
      </div>
    </transition-group>
  </div>
</template>
