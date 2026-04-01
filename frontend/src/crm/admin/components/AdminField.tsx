import type { PropsWithChildren, ReactNode } from "react";

type AdminFieldProps = PropsWithChildren<{
  label: string;
  hint?: ReactNode;
  className?: string;
}>;

export function AdminField({ label, hint, className = "", children }: AdminFieldProps) {
  return (
    <label className={`space-y-2 ${className}`.trim()}>
      <span className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">{label}</span>
      {children}
      {hint ? <span className="block text-xs text-muted-foreground">{hint}</span> : null}
    </label>
  );
}
