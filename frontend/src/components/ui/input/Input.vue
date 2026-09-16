<script setup lang="ts">
import type { HTMLAttributes } from "vue"
import { useVModel } from "@vueuse/core"
import { cn } from "@/lib/utils"
const props = defineProps<{ defaultValue?: string | number; modelValue?: string | number; class?: HTMLAttributes["class"] }>()
const emits = defineEmits<{ (e: "update:modelValue", payload: string | number): void }>()
const modelValue = useVModel(props, "modelValue", emits, { passive: true, defaultValue: props.defaultValue })
</script>
<template>
  <input v-model="modelValue" :class="cn('flex h-10 w-full rounded-xl border border-white/[0.085] bg-black/20 px-3.5 py-2 text-xs text-slate-100 shadow-inner shadow-black/10 ring-offset-background transition-colors placeholder:text-slate-650 focus-visible:border-primary/45 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/10 disabled:cursor-not-allowed disabled:opacity-50', props.class)">
</template>
