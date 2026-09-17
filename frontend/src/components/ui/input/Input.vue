<script setup lang="ts">
import type { HTMLAttributes } from "vue"
import { useVModel } from "@vueuse/core"
import { cn } from "@/lib/utils"
const props = defineProps<{ defaultValue?: string | number; modelValue?: string | number; class?: HTMLAttributes["class"] }>()
const emits = defineEmits<{ (e: "update:modelValue", payload: string | number): void }>()
const modelValue = useVModel(props, "modelValue", emits, { passive: true, defaultValue: props.defaultValue })
</script>
<template>
  <input v-model="modelValue" :class="cn('flex h-10 w-full rounded-xl border border-input bg-card px-3.5 py-2 text-xs text-foreground shadow-sm ring-offset-background transition-colors placeholder:text-muted-foreground/70 focus-visible:border-primary/55 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/15 disabled:cursor-not-allowed disabled:opacity-50', props.class)">
</template>
