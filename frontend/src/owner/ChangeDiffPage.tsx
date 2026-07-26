import { ArrowLeft } from "lucide-react";
import { lazy, Suspense, useEffect, useState } from "react";

import { ownerApi, type OwnerChange } from "./api";
import { formatDate, OwnerBadge, OwnerRouteLoading } from "./components";

const DiffViewer = lazy(() => import("./DiffViewer").then((module) => ({ default: module.DiffViewer })));

export default function ChangeDiffPage({
  changeId,
  onBack,
}: {
  changeId: number;
  onBack: () => void;
}) {
  const [change, setChange] = useState<OwnerChange | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    ownerApi.getChange(changeId)
      .then((response) => {
        if (active) setChange(response.change);
      })
      .catch((reason) => {
        if (active) setError(reason instanceof Error ? reason.message : "Не удалось открыть изменения");
      });
    return () => {
      active = false;
    };
  }, [changeId]);

  if (!change) return <OwnerRouteLoading label={error || "Открываем изменения…"} />;
  return (
    <section>
      <button className="owner-back" onClick={onBack}><ArrowLeft /> К истории</button>
      <div className="owner-detail-heading">
        <div>
          <p className="owner-eyebrow">История модерации</p>
          <h1>{change.camp_name}</h1>
          <p>{change.public_number} · обновлено {formatDate(change.updated_at)}</p>
        </div>
        <OwnerBadge change={change} />
      </div>
      {change.moderator_comment ? <div className="owner-moderator-comment"><b>Комментарий модератора</b>{change.moderator_comment}</div> : null}
      <Suspense fallback={<OwnerRouteLoading label="Готовим сравнение…" />}>
        <DiffViewer items={change.diff_payload || []} title="Что отправлялось" />
      </Suspense>
    </section>
  );
}
