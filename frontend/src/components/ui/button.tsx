import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-[6px] text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#173B3F]/30 disabled:pointer-events-none disabled:opacity-50 cursor-pointer",
  {
    variants: {
      variant: {
        default: "bg-[#C95534] text-white hover:bg-[#B14829] shadow-xs",
        primary: "bg-[#173B3F] text-white hover:bg-[#102B2E] shadow-xs",
        success: "bg-[#2F7D5B] text-white hover:bg-[#256549] shadow-xs",
        marigold: "bg-[#D9911B] text-white hover:bg-[#BE7D13] shadow-xs",
        danger: "bg-[#B84646] text-white hover:bg-[#9C3838] shadow-xs",
        outline:
          "border border-[#CFC8BA] bg-white text-[#173B3F] hover:bg-[#FBF9F5]",
        ghost: "text-[#173B3F] hover:bg-[#EDE8DD]",
      },
      size: {
        sm: "h-7 px-2.5 text-[11px]",
        default: "h-8 px-3 text-xs",
        lg: "h-9 px-4 text-sm",
        icon: "h-8 w-8",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";
