<script setup lang="ts">
import type { HTMLAttributes } from "vue"
import { cn } from "@/lib/utils"
const props = defineProps<{ class?: HTMLAttributes["class"] }>()
</script>
<template>
  <div :class="cn('rounded-[1.1rem] border border-border/90 bg-card/92 text-card-foreground shadow-[0_18px_48px_hsl(var(--shadow-color)/.08)]', props.class)">
    <slot />
  </div>
</template>
