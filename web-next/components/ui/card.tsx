import { cn } from "@/lib/utils";

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("bg-bg-raised border-t-2 border-accent", className)} {...props} />;
}
