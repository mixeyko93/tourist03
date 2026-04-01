import type { ReactNode } from "react";

type AdminStatusBadgeProps = {
  tone: "success" | "warning" | "danger" | "neutral" | "info";
  children: ReactNode;
};

const toneClasses: Record<AdminStatusBadgeProps["tone"], string> = {
  success: "border-emerald-500/20 bg-emerald-500/10 text-emerald-300",
  warning: "border-amber-500/20 bg-amber-500/10 text-amber-300",
  danger: "border-rose-500/20 bg-rose-500/10 text-rose-300",
  neutral: "border-border bg-background/70 text-muted-foreground",
  info: "border-sky-500/20 bg-sky-500/10 text-sky-300",
};

export function AdminStatusBadge({ tone, children }: AdminStatusBadgeProps) {
  return <span className={`inline-flex rounded-full border px-3 py-1 text-xs font-semibold ${toneClasses[tone]}`}>{children}</span>;
}
