<script setup lang="ts">
import type { PopoverContentEmits, PopoverContentProps } from "reka-ui"
import type { HTMLAttributes } from "vue"
import { reactiveOmit } from "@vueuse/core"
import { PopoverContent, PopoverPortal, useForwardPropsEmits } from "reka-ui"
import { cn } from "@/lib/utils"

defineOptions({ inheritAttrs: false })
const props = withDefaults(defineProps<PopoverContentProps & { class?: HTMLAttributes["class"] }>(), { align: "center", sideOffset: 8 })
const emits = defineEmits<PopoverContentEmits>()
const delegatedProps = reactiveOmit(props, "class")
const forwarded = useForwardPropsEmits(delegatedProps, emits)

function handleOpenAutoFocus(event: Event) {
  if (typeof window !== "undefined") {
    // 触控设备或移动视口下彻底禁止打开时自动聚焦，防止键盘遮挡
    const isTouchOrMobile = window.innerWidth < 768 || window.matchMedia("(pointer: coarse)").matches;
    if (isTouchOrMobile) {
      event.preventDefault();
    }
  }
}
</script>
<template>
  <PopoverPortal>
    <PopoverContent
      v-bind="{ ...forwarded, ...$attrs }"
      @open-auto-focus="handleOpenAutoFocus" :class="cn('z-50 w-72 rounded-xl border border-border bg-popover p-4 text-popover-foreground shadow-[0_22px_64px_hsl(var(--shadow-color)/.25)] outline-none data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95', props.class)">
      <slot />
    </PopoverContent>
  </PopoverPortal>
</template>
