import type { VariantProps } from "class-variance-authority"
import { cva } from "class-variance-authority"

export { default as Badge } from "./Badge.vue"

export const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-[10px] font-semibold tracking-normal transition-colors focus:outline-none focus:ring-2 focus:ring-ring/60 focus:ring-offset-2 select-none",
  {
    variants: {
      variant: {
        default: "border-border bg-muted text-muted-foreground",
        brand: "border-primary/20 bg-primary/10 text-primary",
        primary: "border-primary/20 bg-primary/10 text-primary",
        secondary: "border-border bg-secondary text-secondary-foreground",
        destructive: "border-destructive/20 bg-destructive/10 text-destructive",
        outline: "border-border bg-transparent text-muted-foreground",
        success: "border-emerald-500/20 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
        amber: "border-amber-500/20 bg-amber-500/10 text-amber-700 dark:text-amber-400",
        indigo: "border-indigo-500/20 bg-indigo-500/10 text-indigo-600 dark:text-indigo-400",
      },
    },
    defaultVariants: { variant: "default" },
  },
)

export type BadgeVariants = VariantProps<typeof badgeVariants>
