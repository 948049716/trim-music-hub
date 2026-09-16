<script setup lang="ts">
import type { SelectTriggerProps } from "reka-ui"
import type { HTMLAttributes } from "vue"
import { reactiveOmit } from "@vueuse/core"
import { ChevronDown } from "lucide-vue-next"
import { SelectIcon, SelectTrigger, useForwardProps } from "reka-ui"
import { cn } from "@/lib/utils"
const props = defineProps<SelectTriggerProps & { class?: HTMLAttributes["class"] }>()
const delegatedProps = reactiveOmit(props, "class")
const forwardedProps = useForwardProps(delegatedProps)
</script>
<template>
  <SelectTrigger
    v-bind="forwardedProps"
    :class="cn('flex h-10 w-full items-center justify-between rounded-xl border border-white/[0.085] bg-black/20 px-3.5 py-2 text-xs text-slate-200 shadow-inner shadow-black/10 ring-offset-background transition-colors data-[placeholder]:text-slate-600 focus:border-primary/45 focus:outline-none focus:ring-2 focus:ring-primary/10 disabled:cursor-not-allowed disabled:opacity-50 [&>span]:truncate text-start', props.class)"
  >
    <slot />
    <SelectIcon as-child><ChevronDown class="h-3.5 w-3.5 shrink-0 text-slate-600" /></SelectIcon>
  </SelectTrigger>
</template>
