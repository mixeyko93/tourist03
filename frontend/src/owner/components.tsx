import type { CSSProperties, ReactNode } from "react";

import type { OwnerChange } from "./api";

const STATUS_CLASS: Record<string, string> = {
  draft: "neutral",
  submitted: "info",
  in_review: "info",
  needs_changes: "warning",
  approved: "success",
  applied: "success",
  rejected: "danger",
  withdrawn: "neutral",
  archived: "neutral",
};

export function formatDate(value?: string | null, withTime = true) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "long",
    year: "numeric",
    ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
  }).format(date);
}

export function OwnerBadge({ change }: { change: Pick<OwnerChange, "status" | "status_label"> }) {
  return <span className={`owner-badge ${STATUS_CLASS[change.status] || "neutral"}`}>{change.status_label}</span>;
}

export function QualityRing({ score, compact = false }: { score: number; compact?: boolean }) {
  return (
    <div
      className={`owner-quality-ring ${compact ? "compact" : ""}`}
      style={{ "--owner-progress": `${Math.max(0, Math.min(score, 100)) * 3.6}deg` } as CSSProperties}
      role="img"
      aria-label={`Карточка заполнена на ${score}%`}
    >
      <span>{score}%</span>
    </div>
  );
}

export function OwnerRouteLoading({ label = "Загружаем раздел…" }: { label?: string }) {
  return (
    <div className="owner-route-loading" role="status" aria-live="polite">
      <span aria-hidden="true" />
      <p>{label}</p>
    </div>
  );
}

export function OwnerRouteError({ children }: { children: ReactNode }) {
  return (
    <section className="owner-card owner-route-error" role="alert">
      <h1>Раздел не загрузился</h1>
      <p>{children}</p>
      <button className="owner-primary" onClick={() => window.location.reload()}>
        Повторить загрузку
      </button>
    </section>
  );
}
