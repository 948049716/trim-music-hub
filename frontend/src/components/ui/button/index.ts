import type { VariantProps } from "class-variance-authority"
import { cva } from "class-variance-authority"

export { default as Button } from "./Button.vue"

export const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-xs font-medium ring-offset-background transition-[background-color,border-color,color,box-shadow,transform] duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/70 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-40 select-none cursor-pointer active:translate-y-px [&_svg]:pointer-events-none [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "border border-primary/35 bg-primary text-primary-foreground shadow-[0_8px_24px_rgba(16,185,129,.14)] hover:bg-primary/90",
        destructive: "border border-destructive/40 bg-destructive text-destructive-foreground hover:bg-destructive/90",
        destructiveOutline: "border border-destructive/25 bg-destructive/[0.07] text-rose-400 hover:border-destructive/40 hover:bg-destructive/[0.12]",
        outline: "border border-white/[0.09] bg-white/[0.025] text-slate-300 hover:border-white/[0.14] hover:bg-white/[0.055] hover:text-white",
        secondary: "border border-white/[0.06] bg-white/[0.055] text-slate-200 hover:bg-white/[0.085]",
        ghost: "border border-transparent text-slate-400 hover:bg-white/[0.05] hover:text-white",
        link: "text-primary underline-offset-4 hover:underline",
        brand: "border border-primary/35 bg-primary text-primary-foreground shadow-[0_8px_24px_rgba(16,185,129,.14)] hover:bg-primary/90",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 px-3 text-[11px]",
        lg: "h-10 px-4 text-xs",
        icon: "h-9 w-9 p-0",
        iconSm: "h-7 w-7 p-0",
        "icon-sm": "h-7 w-7 p-0",
        "icon-lg": "h-10 w-10 p-0",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
)

export type ButtonVariants = VariantProps<typeof buttonVariants>
