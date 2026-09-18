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
        success: "border-success/25 bg-success/15 text-success",
        warning: "border-warning/25 bg-warning/15 text-warning",
        amber: "border-warning/25 bg-warning/15 text-warning",
        info: "border-info/25 bg-info/15 text-info",
        indigo: "border-info/25 bg-info/15 text-info",
      },
    },
    defaultVariants: { variant: "default" },
  },
)

export type BadgeVariants = VariantProps<typeof badgeVariants>
