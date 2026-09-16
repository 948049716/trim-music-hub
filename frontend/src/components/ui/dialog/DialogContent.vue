<script setup lang="ts">
import type { DialogContentEmits, DialogContentProps } from "reka-ui"
import type { HTMLAttributes } from "vue"
import { reactiveOmit } from "@vueuse/core"
import { X } from "lucide-vue-next"
import { DialogClose, DialogContent, DialogOverlay, DialogPortal, useForwardPropsEmits } from "reka-ui"
import { cn } from "@/lib/utils"
const props = defineProps<DialogContentProps & { class?: HTMLAttributes["class"] }>()
const emits = defineEmits<DialogContentEmits>()
const delegatedProps = reactiveOmit(props, "class")
const forwarded = useForwardPropsEmits(delegatedProps, emits)
</script>
<template>
  <DialogPortal>
    <DialogOverlay class="fixed inset-0 z-50 bg-black/65 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
    <DialogContent
      v-bind="forwarded"
      :class="cn('fixed left-1/2 top-1/2 z-50 grid w-[calc(100%-2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 gap-4 rounded-2xl border border-white/[0.09] bg-[#0d1412]/95 p-6 shadow-[0_30px_100px_rgba(0,0,0,.55)] backdrop-blur-2xl duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95', props.class)"
    >
      <slot />
      <DialogClose class="absolute right-4 top-4 flex h-8 w-8 items-center justify-center rounded-lg text-slate-600 transition-colors hover:bg-white/[0.06] hover:text-white focus:outline-none focus:ring-2 focus:ring-primary/30">
        <X class="h-4 w-4" /><span class="sr-only">关闭</span>
      </DialogClose>
    </DialogContent>
  </DialogPortal>
</template>
