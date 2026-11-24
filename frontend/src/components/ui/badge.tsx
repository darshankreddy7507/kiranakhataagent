import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-[4px] border px-2 py-0.5 text-[11px] font-medium leading-tight whitespace-nowrap",
  {
    variants: {
      variant: {
        neutral: "border-[#DDD7CA] bg-[#F7F4EE] text-[#4D6265]",
        teal: "border-[#173B3F]/20 bg-[#173B3F]/8 text-[#173B3F]",
        marigold: "border-[#D9911B]/35 bg-[#D9911B]/12 text-[#8E5C08]",
        green: "border-[#2F7D5B]/30 bg-[#2F7D5B]/10 text-[#226045]",
        red: "border-[#B84646]/30 bg-[#B84646]/10 text-[#963232]",
        terracotta: "border-[#C95534]/30 bg-[#C95534]/10 text-[#9D3E23]",
      },
    },
    defaultVariants: {
      variant: "neutral",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
