import { ArrowLeft, Check, PencilLine, X } from "lucide-react";
import { lazy, Suspense, useEffect, useState } from "react";

import { ownerApi, type EntitySchema, type OwnerCamp, type OwnerChange } from "./api";
import { OwnerBadge, OwnerRouteLoading, QualityRing } from "./components";

const OwnerEditor = lazy(() => import("./OwnerEditor"));

type CampDetailData = {
  camp: Record<string, unknown>;
  quality: OwnerCamp["quality"];
  changes: OwnerChange[];
  amenity_catalog: Array<{ id: number; name: string; category: string }>;
  entity_schema?: EntitySchema | null;
};

export default function CampPage({
  camp,
  campId,
  changeRequestsEnabled,
  onBack,
  onReload,
}: {
  camp?: OwnerCamp;
  campId: number;
  changeRequestsEnabled: boolean;
  onBack: () => void;
  onReload: () => void;
}) {
  const [detail, setDetail] = useState<CampDetailData | null>(null);
  const [change, setChange] = useState<OwnerChange | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    let active = true;
    ownerApi.camp(campId)
      .then(async (response) => {
        if (!active) return;
        setDetail(response);
        const editable = response.changes.find((item) =>
          ["draft", "needs_changes", "withdrawn"].includes(item.status));
        if (editable) {
          const full = await ownerApi.getChange(editable.id);
          if (active) setChange(full.change);
        }
      })
      .catch((reason) => {
        if (active) setError(reason instanceof Error ? reason.message : "Ошибка загрузки");
      });
    return () => {
      active = false;
    };
  }, [campId]);

  async function beginEdit() {
    setError("");
    try {
      const result = await ownerApi.createChange(campId);
      setChange(result.change);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось создать черновик");
    }
  }

  async function requestPublication() {
    setError("");
    try {
      const draft = await ownerApi.createChange(campId);
      const saved = await ownerApi.saveChange(
        draft.change.id,
        draft.change.content_version,
        { ...draft.change.proposed_payload, request_publication: true },
      );
      setChange(saved.change);
      setMessage("Запрос на повторную публикацию подготовлен. Проверьте и отправьте его.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось подготовить запрос");
    }
  }

  if (!detail) return <OwnerRouteLoading label={error || "Открываем карточку…"} />;
  const currentCamp = camp ?? {
    id: campId,
    name: String(detail.camp.name || "Объект"),
    slug: typeof detail.camp.slug === "string" ? detail.camp.slug : null,
    place_type_name: typeof detail.camp.place_type_name === "string" ? detail.camp.place_type_name : null,
    subtype: typeof detail.camp.subtype === "string" ? detail.camp.subtype : null,
    entity_kind: typeof detail.camp.entity_kind === "string" ? detail.camp.entity_kind as OwnerCamp["entity_kind"] : null,
    entity_kind_name: null,
    schema_key: typeof detail.camp.schema_key === "string" ? detail.camp.schema_key : null,
    schema_version: typeof detail.camp.schema_version === "number" ? detail.camp.schema_version : null,
    publication_status: String(detail.camp.publication_status || "draft"),
    role_key: "owner",
    is_primary: true,
    pending_changes: detail.changes.filter((item) => ["draft", "submitted", "in_review", "needs_changes"].includes(item.status)).length,
    quality: detail.quality,
    statistics: {},
  };
  return (
    <section>
      <button className="owner-back" onClick={onBack}><ArrowLeft /> К списку объектов</button>
      <div className="owner-detail-heading">
        <div>
          <p className="owner-eyebrow">{currentCamp.entity_kind_name || currentCamp.place_type_name || "Управление карточкой"}</p>
          <h1>{currentCamp.name}</h1>
          <p>{detail.camp.address ? String(detail.camp.address) : "Адрес не указан"}</p>
        </div>
        {!change && changeRequestsEnabled ? <div className="owner-heading-actions"><button className="owner-primary" onClick={() => void beginEdit()}><PencilLine /> Предложить изменения</button>{currentCamp.publication_status !== "published" ? <button className="owner-secondary" onClick={() => void requestPublication()}>Запросить публикацию</button> : null}</div> : change && changeRequestsEnabled ? <OwnerBadge change={change} /> : null}
      </div>
      {error ? <p className="owner-alert danger" role="alert">{error}</p> : null}
      {message ? <p className="owner-alert success" role="status">{message}</p> : null}
      <div className="owner-detail-grid">
        <section className="owner-card owner-quality-panel">
          <QualityRing score={detail.quality.score} />
          <div><h2>Карточка заполнена на {detail.quality.score}%</h2><div className="owner-progress"><span style={{ width: `${detail.quality.score}%` }} /></div></div>
          <ul>{detail.quality.checklist.map((item) => <li key={item.key} className={item.complete ? "complete" : ""}>{item.complete ? <Check /> : <X />}{item.label}</li>)}</ul>
        </section>
        <section className="owner-card owner-health-panel"><h2>Состояние объекта</h2>{detail.quality.health.map((item) => <div key={item.key} className={item.level}><span />{item.label}</div>)}</section>
      </div>
      {changeRequestsEnabled && change && ["draft", "needs_changes", "withdrawn"].includes(change.status) ? (
        <Suspense fallback={<OwnerRouteLoading label="Открываем редактор…" />}>
          <OwnerEditor
            detail={detail}
            schema={detail.entity_schema}
            initialChange={change}
            onChange={setChange}
            onSubmitted={onReload}
            onMessage={setMessage}
            onError={setError}
          />
        </Suspense>
      ) : null}
      {currentCamp.publication_status === "published" ? <section className="owner-card owner-danger-zone"><div><h2>Снять объект с публикации</h2><p>Карточка исчезнет из каталога сразу. Повторная публикация потребует проверки.</p></div><button onClick={async () => { if (window.confirm("Снять объект с публикации?")) { await ownerApi.unpublish(campId); onReload(); } }}>Снять с публикации</button></section> : null}
    </section>
  );
}
