import type { LucideIcon } from "lucide-react";

type EmptyStateProps = {
  icon: LucideIcon;
  title: string;
  description: string;
  compact?: boolean;
};

export function EmptyState({ icon: Icon, title, description, compact = false }: EmptyStateProps) {
  return (
    <div
      className={`rounded-[1.8rem] border border-dashed border-[#2F80ED]/25 bg-background/60 text-center ${
        compact ? "px-5 py-8" : "px-6 py-12"
      }`}
    >
      <span className="mx-auto inline-flex h-12 w-12 items-center justify-center rounded-2xl border border-[#2F80ED]/25 bg-[#2F80ED]/10 text-[#2F80ED]">
        <Icon className="h-5 w-5" />
      </span>
      <h2 className="mt-4 text-lg font-semibold tracking-[-0.03em] text-foreground">{title}</h2>
      <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-muted-foreground">{description}</p>
    </div>
  );
}
