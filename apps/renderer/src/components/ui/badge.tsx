import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium",
  {
    variants: {
      variant: {
        muted: "bg-muted text-muted-foreground",
        success: "bg-success/12 text-success",
        destructive: "bg-destructive/12 text-destructive",
        warning: "bg-warning/14 text-warning"
      }
    },
    defaultVariants: {
      variant: "muted"
    }
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant, className }))} {...props} />;
}
