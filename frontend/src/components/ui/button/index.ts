import type { VariantProps } from "class-variance-authority"
import { cva } from "class-variance-authority"

export { default as Button } from "./Button.vue"

export const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-xs font-semibold ring-offset-background transition-[background-color,border-color,color,box-shadow,transform] duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-45 select-none cursor-pointer active:translate-y-px [&_svg]:pointer-events-none [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "border border-primary/80 bg-primary text-primary-foreground shadow-sm hover:bg-primary/90",
        destructive: "border border-destructive/80 bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90",
        destructiveOutline: "border border-destructive/25 bg-destructive/[0.07] text-destructive hover:bg-destructive/[0.12]",
        outline: "border border-border bg-card/70 text-foreground hover:border-primary/30 hover:bg-muted",
        secondary: "border border-border/70 bg-secondary text-secondary-foreground hover:bg-secondary/75",
        ghost: "border border-transparent text-muted-foreground hover:bg-muted hover:text-foreground",
        link: "text-primary underline-offset-4 hover:underline",
        brand: "border border-primary/80 bg-primary text-primary-foreground shadow-sm hover:bg-primary/90",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-8 px-3 text-[11px]",
        lg: "h-11 px-4 text-xs",
        icon: "h-10 w-10 p-0",
        iconSm: "h-8 w-8 p-0",
        "icon-sm": "h-8 w-8 p-0",
        "icon-lg": "h-11 w-11 p-0",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
)

export type ButtonVariants = VariantProps<typeof buttonVariants>
