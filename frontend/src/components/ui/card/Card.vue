<script setup lang="ts">
import type { HTMLAttributes } from "vue"
import { cn } from "@/lib/utils"
const props = defineProps<{ class?: HTMLAttributes["class"] }>()
</script>
<template>
  <div :class="cn('rounded-2xl border border-white/[0.07] bg-card/85 text-card-foreground shadow-[0_18px_60px_rgba(0,0,0,.16)]', props.class)">
    <slot />
  </div>
</template>
