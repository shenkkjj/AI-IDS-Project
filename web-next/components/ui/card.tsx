import { cn } from "@/lib/utils";

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-xl border border-cyan-200/20 bg-slate-900/70 shadow-neon", className)} {...props} />;
}
