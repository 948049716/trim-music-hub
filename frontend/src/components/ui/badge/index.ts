import type { VariantProps } from "class-variance-authority"
import { cva } from "class-variance-authority"

export { default as Badge } from "./Badge.vue"

export const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-[10px] font-medium tracking-wide transition-colors focus:outline-none focus:ring-2 focus:ring-ring/60 focus:ring-offset-2 select-none",
  {
    variants: {
      variant: {
        default: "border-white/[0.06] bg-white/[0.05] text-slate-300",
        brand: "border-primary/20 bg-primary/10 text-emerald-400",
        primary: "border-primary/20 bg-primary/10 text-emerald-400",
        secondary: "border-white/[0.06] bg-white/[0.05] text-slate-300",
        destructive: "border-destructive/20 bg-destructive/10 text-rose-400",
        success: "border-emerald-500/20 bg-emerald-500/10 text-emerald-400",
        indigo: "border-indigo-500/20 bg-indigo-500/10 text-indigo-400",
        amber: "border-amber-500/20 bg-amber-500/10 text-amber-400",
        outline: "border-white/[0.09] bg-transparent text-slate-500",
      },
    },
    defaultVariants: { variant: "default" },
  },
)

export type BadgeVariants = VariantProps<typeof badgeVariants>
