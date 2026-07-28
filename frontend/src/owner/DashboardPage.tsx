import {
  Activity,
  Building2,
  Check,
  ChevronRight,
  CircleAlert,
  Clock3,
  Sparkles,
} from "./initialIcons";
import { Plus } from "lucide-react";

import type { OwnerCamp, OwnerDashboard } from "./api";
import { formatDate, OwnerBadge, QualityRing } from "./components";

export default function DashboardPage({
  data,
  onCamp,
  onChanges,
  onCreate,
  canCreate,
}: {
  data: OwnerDashboard;
  onCamp: (camp: OwnerCamp) => void;
  onChanges: () => void;
  onCreate: () => void;
  canCreate: boolean;
}) {
  const firstName = data.owner.display_name.split(" ")[0] || "владелец";
  return (
    <>
      <section className="owner-welcome">
        <div>
          <p className="owner-eyebrow">Обзор объектов</p>
          <h1>Здравствуйте, {firstName}</h1>
          <p>Здесь сразу видно, что происходит с карточками и что требует внимания.</p>
        </div>
        <div className="owner-welcome-actions">
          <div className="owner-summary-pill"><Clock3 /><span><b>{data.profile_statistics.pending_changes}</b> ожидают проверки</span></div>
          {canCreate ? <button type="button" className="owner-primary" onClick={onCreate}><Plus /> Добавить карточку</button> : null}
        </div>
      </section>
      <section className="owner-metric-grid">
        <article><Building2 /><span>Ваши объекты</span><strong>{data.profile_statistics.objects_count}</strong></article>
        <article><Clock3 /><span>Ожидают проверки</span><strong>{data.profile_statistics.pending_changes}</strong></article>
        <article><Check /><span>Одобрено изменений</span><strong>{data.profile_statistics.approved_changes}</strong></article>
        <article><CircleAlert /><span>Требуют внимания</span><strong>{data.attention.length}</strong></article>
      </section>
      <div className="owner-dashboard-grid">
        <section className="owner-card owner-objects-overview">
          <div className="owner-section-heading"><div><p className="owner-eyebrow">Состояние карточек</p><h2>Мои объекты</h2></div></div>
          <div className="owner-object-list">
            {data.camps.map((camp) => (
              <button key={camp.id} className="owner-object-row" onClick={() => onCamp(camp)}>
                <QualityRing score={camp.quality.score} compact />
                <span className="owner-object-copy">
                  <b>{camp.name}</b>
                  <small>{camp.entity_kind_name || "Туристический объект"} · {camp.place_type_name || camp.subtype || "Тип не указан"}</small>
                  <small>{camp.publication_status === "published" ? "Опубликован" : "Не опубликован"} · {camp.pending_changes} на проверке</small>
                </span>
                <ChevronRight />
              </button>
            ))}
            {!data.camps.length ? (
              <div className="owner-empty-action">
                <p className="owner-empty">С аккаунтом пока не связана ни одна карточка.</p>
                {canCreate ? <button type="button" className="owner-secondary" onClick={onCreate}><Plus /> Добавить первую</button> : null}
              </div>
            ) : null}
          </div>
        </section>
        <section className="owner-card owner-attention">
          <div className="owner-section-heading"><div><p className="owner-eyebrow">Следующий шаг</p><h2>Стоит улучшить</h2></div><Sparkles /></div>
          <ul>
            {data.attention.slice(0, 6).map((item, index) => (
              <li key={`${item.camp_id}-${index}`}><CircleAlert /><span><b>{item.camp_name}</b>{item.message}</span></li>
            ))}
          </ul>
          {!data.attention.length ? <p className="owner-empty">Отлично: обязательные блоки карточек заполнены.</p> : null}
        </section>
        {data.features.change_requests ? <section className="owner-card owner-pending">
          <div className="owner-section-heading"><div><p className="owner-eyebrow">Модерация</p><h2>Изменения на проверке</h2></div><button className="owner-text-action" onClick={onChanges}>Все изменения</button></div>
          {data.pending_changes.map((change) => (
            <div className="owner-change-line" key={change.id}><div><b>{change.camp_name}</b><small>{change.public_number} · {formatDate(change.updated_at)}</small></div><OwnerBadge change={change} /></div>
          ))}
          {!data.pending_changes.length ? <p className="owner-empty">Сейчас нет изменений, ожидающих решения.</p> : null}
        </section> : null}
        <section className="owner-card owner-activity">
          <div className="owner-section-heading"><div><p className="owner-eyebrow">Последние события</p><h2>Активность</h2></div><Activity /></div>
          <div className="owner-timeline">
            {data.activity.map((event) => {
              const camp = data.camps.find((item) => item.id === event.camp_id);
              return (
                <div key={event.id}>
                  <span className="owner-timeline-dot"><Check /></span>
                  {event.action_url && camp ? (
                    <button className="owner-activity-link" onClick={() => onCamp(camp)}>
                      <b>{event.description}</b><small>{formatDate(event.created_at)}</small>
                    </button>
                  ) : <p><b>{event.description}</b><small>{formatDate(event.created_at)}</small></p>}
                </div>
              );
            })}
            {!data.activity.length ? <p className="owner-empty">События появятся после первого изменения.</p> : null}
          </div>
        </section>
      </div>
    </>
  );
}
