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

function handleOpenAutoFocus(event: Event) {
  if (typeof window !== "undefined") {
    // 触控设备或移动视口下彻底禁止打开时自动聚焦输入框，防止输入法键盘遮挡界面
    const isTouchOrMobile = window.innerWidth < 768 || window.matchMedia("(pointer: coarse)").matches;
    if (isTouchOrMobile) {
      event.preventDefault();
    }
  }
}
</script>

<template>
  <DialogPortal>
    <DialogOverlay class="fixed inset-0 z-50 bg-slate-950/48 backdrop-blur-[3px] data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
    <DialogContent
      v-bind="{ ...forwarded, ...$attrs }"
      @open-auto-focus="handleOpenAutoFocus"
      :class="cn('fixed inset-x-3 bottom-3 z-50 grid max-h-[calc(100dvh-1.5rem)] gap-4 overflow-y-auto rounded-[1.25rem] border border-border bg-popover p-5 pb-[calc(1.25rem+env(safe-area-inset-bottom,0px))] text-popover-foreground shadow-[0_24px_80px_hsl(var(--shadow-color)/.32)] duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:slide-out-to-bottom-3 data-[state=open]:slide-in-from-bottom-3 sm:left-[50%] sm:top-[50%] sm:bottom-auto sm:w-full sm:max-w-lg sm:-translate-x-1/2 sm:-translate-y-1/2 sm:p-6 sm:data-[state=closed]:zoom-out-95 sm:data-[state=open]:zoom-in-95', props.class)"
    >
      <slot />
      <DialogClose class="absolute right-3 top-3 grid h-8 w-8 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus:outline-none focus:ring-2 focus:ring-ring/50 disabled:pointer-events-none">
        <X class="h-4 w-4" />
        <span class="sr-only">关闭</span>
      </DialogClose>
    </DialogContent>
  </DialogPortal>
</template>
