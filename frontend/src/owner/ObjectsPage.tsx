import { ChevronRight, CircleAlert } from "lucide-react";
import { useState } from "react";

import { ownerApi, type OwnerCamp, type OwnerDashboard } from "./api";
import { QualityRing } from "./components";

export default function ObjectsPage({
  dashboard,
  onCamp,
  onCampsLoaded,
}: {
  dashboard: OwnerDashboard;
  onCamp: (camp: OwnerCamp) => void;
  onCampsLoaded: (camps: OwnerCamp[], pagination: OwnerDashboard["object_pagination"]) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function loadMore() {
    setBusy(true);
    setError("");
    try {
      const response = await ownerApi.camps(
        dashboard.object_pagination.limit,
        dashboard.camps.length,
      );
      onCampsLoaded(
        [...dashboard.camps, ...response.camps],
        response.pagination,
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось загрузить объекты");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section>
      <div className="owner-page-heading"><div><p className="owner-eyebrow">Портфель</p><h1>Мои объекты</h1><p>Заполненность, состояние публикации и ожидающие изменения.</p></div></div>
      <div className="owner-camp-grid">
        {dashboard.camps.map((camp) => (
          <button key={camp.id} className="owner-camp-card" onClick={() => onCamp(camp)}>
            <div className="owner-camp-card-top"><QualityRing score={camp.quality.score} /><span className={`owner-publication ${camp.publication_status === "published" ? "live" : ""}`}>{camp.publication_status === "published" ? "Опубликован" : "Не опубликован"}</span></div>
            <h2>{camp.name}</h2>
            <p>{camp.place_type_name || "Туристический объект"} · карточка заполнена на {camp.quality.score}%</p>
            <div className="owner-progress"><span style={{ width: `${camp.quality.score}%` }} /></div>
            <ul>{camp.quality.recommendations.slice(0, 3).map((item) => <li key={item}><CircleAlert />{item}</li>)}</ul>
            <span className="owner-open">Открыть объект <ChevronRight /></span>
          </button>
        ))}
      </div>
      {error ? <p className="owner-alert danger" role="alert">{error}</p> : null}
      {dashboard.object_pagination.has_more ? (
        <button className="owner-secondary owner-load-more" disabled={busy} onClick={() => void loadMore()}>
          {busy ? "Загружаем…" : "Показать ещё"}
        </button>
      ) : null}
    </section>
  );
}
