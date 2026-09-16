<script setup lang="ts">
import type { TabsListProps } from "reka-ui"
import type { HTMLAttributes } from "vue"
import { reactiveOmit } from "@vueuse/core"
import { TabsList } from "reka-ui"
import { cn } from "@/lib/utils"
const props = defineProps<TabsListProps & { class?: HTMLAttributes["class"] }>()
const delegatedProps = reactiveOmit(props, "class")
</script>
<template>
  <TabsList v-bind="delegatedProps" :class="cn('inline-flex items-center justify-center rounded-xl border border-white/[0.06] bg-black/20 p-1 text-slate-500', props.class)">
    <slot />
  </TabsList>
</template>
