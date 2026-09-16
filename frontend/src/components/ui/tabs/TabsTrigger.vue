<script setup lang="ts">
import type { TabsTriggerProps } from "reka-ui"
import type { HTMLAttributes } from "vue"
import { reactiveOmit } from "@vueuse/core"
import { TabsTrigger, useForwardProps } from "reka-ui"
import { cn } from "@/lib/utils"
const props = defineProps<TabsTriggerProps & { class?: HTMLAttributes["class"] }>()
const delegatedProps = reactiveOmit(props, "class")
const forwardedProps = useForwardProps(delegatedProps)
</script>
<template>
  <TabsTrigger
    v-bind="forwardedProps"
    :class="cn('inline-flex items-center justify-center whitespace-nowrap rounded-lg px-3 py-1.5 text-[11px] font-medium text-slate-500 ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 hover:text-slate-200 data-[state=active]:bg-white/[0.075] data-[state=active]:text-white data-[state=active]:shadow-sm cursor-pointer select-none', props.class)"
  >
    <span class="flex items-center gap-1.5 truncate"><slot /></span>
  </TabsTrigger>
</template>
