import { ChevronRight } from "lucide-react";
import { useEffect, useState } from "react";

import { ownerApi, type OwnerChange } from "./api";
import { formatDate, OwnerBadge, OwnerRouteLoading } from "./components";

export default function HistoryPage({
  cachedChanges,
  onLoaded,
  onOpen,
}: {
  cachedChanges: OwnerChange[] | null;
  onLoaded: (changes: OwnerChange[]) => void;
  onOpen: (change: OwnerChange) => void;
}) {
  const [changes, setChanges] = useState<OwnerChange[] | null>(cachedChanges);
  const [pagination, setPagination] = useState({ limit: 30, offset: 0, total: cachedChanges?.length || 0, has_more: false });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (changes !== null) return;
    setBusy(true);
    ownerApi.changes()
      .then((response) => {
        setChanges(response.changes);
        setPagination(response.pagination);
        onLoaded(response.changes);
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Не удалось загрузить историю"))
      .finally(() => setBusy(false));
  }, [changes, onLoaded]);

  async function loadMore() {
    if (!changes) return;
    setBusy(true);
    setError("");
    try {
      const response = await ownerApi.changes(pagination.limit, changes.length);
      const next = [...changes, ...response.changes];
      setChanges(next);
      setPagination(response.pagination);
      onLoaded(next);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось загрузить историю");
    } finally {
      setBusy(false);
    }
  }

  if (changes === null && busy) return <OwnerRouteLoading label="Загружаем историю…" />;
  return (
    <section>
      <div className="owner-page-heading"><div><p className="owner-eyebrow">История модерации</p><h1>Изменения</h1><p>Что отправлялось, когда и с каким результатом.</p></div></div>
      {error ? <p className="owner-alert danger" role="alert">{error}</p> : null}
      <div className="owner-history-list">
        {(changes || []).map((change) => (
          <article className="owner-card" key={change.id}>
            <div className="owner-change-line"><div><h2>{change.camp_name}</h2><small>{change.public_number} · создано {formatDate(change.created_at)}</small></div><OwnerBadge change={change} /></div>
            <p>{change.diff_count || 0} изменённых полей</p>
            {change.moderator_comment ? <div className="owner-moderator-comment"><b>Комментарий модератора</b>{change.moderator_comment}</div> : null}
            <div className="owner-history-meta">
              <span>Отправлено: {formatDate(change.submitted_at)}</span>
              <span>Решение: {formatDate(change.decided_at)}</span>
            </div>
            <button className="owner-text-action owner-change-open" onClick={() => onOpen(change)}>
              Открыть эти изменения <ChevronRight />
            </button>
          </article>
        ))}
        {changes && !changes.length ? <p className="owner-empty owner-card">История пока пуста.</p> : null}
      </div>
      {pagination.has_more ? (
        <button className="owner-secondary owner-load-more" disabled={busy} onClick={() => void loadMore()}>
          {busy ? "Загружаем…" : "Показать ещё"}
        </button>
      ) : null}
    </section>
  );
}
