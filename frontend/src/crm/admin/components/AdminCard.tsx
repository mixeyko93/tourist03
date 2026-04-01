import type { PropsWithChildren } from "react";

type AdminCardProps = PropsWithChildren<{
  className?: string;
}>;

export function AdminCard({ children, className = "" }: AdminCardProps) {
  return <section className={`admin-card ${className}`.trim()}>{children}</section>;
}
