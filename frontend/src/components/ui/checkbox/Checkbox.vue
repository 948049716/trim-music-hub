<script setup lang="ts">
import type { CheckboxRootProps } from "reka-ui"
import type { HTMLAttributes } from "vue"
import { computed } from "vue"
import { Check } from "lucide-vue-next"
import { CheckboxIndicator, CheckboxRoot } from "reka-ui"
import { cn } from "@/lib/utils"

interface Props extends /* @vue-ignore */ Partial<CheckboxRootProps> {
  class?: HTMLAttributes["class"]
  checked?: boolean | "indeterminate"
  modelValue?: boolean | "indeterminate"
  disabled?: boolean
  id?: string
  name?: string
  required?: boolean
  value?: any
}

const props = withDefaults(defineProps<Props>(), {
  checked: undefined,
  modelValue: undefined,
  disabled: false,
})

const emit = defineEmits<{
  (e: "update:modelValue", value: boolean | "indeterminate"): void
  (e: "update:checked", value: boolean): void
}>()

const innerChecked = computed<boolean | "indeterminate">({
  get() {
    if (props.modelValue !== undefined) return props.modelValue
    if (props.checked !== undefined) return props.checked
    return false
  },
  set(val) {
    emit("update:modelValue", val)
    emit("update:checked", Boolean(val))
  }
})
</script>

<template>
  <CheckboxRoot
    v-model="innerChecked"
    :disabled="props.disabled"
    :id="props.id"
    :name="props.name"
    :required="props.required"
    :value="props.value"
    :class="
      cn('grid place-content-center peer h-4 w-4 shrink-0 rounded-sm border border-primary ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground',
         props.class)"
  >
    <CheckboxIndicator class="grid place-content-center text-current">
      <slot>
        <Check class="h-4 w-4" />
      </slot>
    </CheckboxIndicator>
  </CheckboxRoot>
</template>
