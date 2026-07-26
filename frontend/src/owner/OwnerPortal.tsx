import {
  Activity,
  ArrowLeft,
  Building2,
  Check,
  ChevronRight,
  CircleAlert,
  Clock3,
  FileClock,
  LayoutDashboard,
  LogOut,
  Menu,
  PencilLine,
  Send,
  ShieldCheck,
  Sparkles,
  UserRound,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { CSSProperties, FormEvent } from "react";
import { DiffViewer } from "./DiffViewer";
import {
  ownerApi,
  type ChangeDiff,
  type OwnerCamp,
  type OwnerChange,
  type OwnerDashboard,
  type OwnerProfile,
} from "./api";
import "./owner.css";

type View = "dashboard" | "objects" | "changes" | "profile";

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

function formatDate(value?: string | null, withTime = true) {
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

function OwnerBadge({ change }: { change: Pick<OwnerChange, "status" | "status_label"> }) {
  return <span className={`owner-badge ${STATUS_CLASS[change.status] || "neutral"}`}>{change.status_label}</span>;
}

function QualityRing({ score, compact = false }: { score: number; compact?: boolean }) {
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

function LoginScreen({ onLogin }: { onLogin: (owner: OwnerProfile) => void }) {
  const token = new URLSearchParams(window.location.search).get("token") || "";
  const [mode, setMode] = useState<"login" | "forgot" | "reset">(token ? "reset" : "login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      if (mode === "login") {
        const result = await ownerApi.login(email, password);
        onLogin(result.owner);
      } else if (mode === "forgot") {
        const result = await ownerApi.forgot(email);
        setMessage(result.message);
      } else {
        const result = await ownerApi.reset(token, password);
        setMessage(result.message);
        window.history.replaceState({}, "", "/owner");
        setMode("login");
        setPassword("");
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось выполнить действие");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="owner-auth">
      <section className="owner-auth-brand">
        <img src="/static/brand/turistika-logo-horizontal-dark.svg" width="720" height="180" alt="Туристика" />
        <div>
          <p className="owner-eyebrow">Кабинет владельца</p>
          <h1>Ваша карточка работает лучше, когда всё под контролем.</h1>
          <p>Обновляйте информацию, отправляйте изменения на проверку и следите за состоянием объектов в одном месте.</p>
        </div>
        <ul>
          <li><ShieldCheck /> Публикация только после проверки</li>
          <li><Sparkles /> Подсказки по улучшению карточки</li>
          <li><FileClock /> Полная история изменений</li>
        </ul>
      </section>
      <section className="owner-auth-panel">
        <form className="owner-auth-form" onSubmit={submit}>
          <img src="/static/brand/turistika-icon.svg" width="160" height="160" alt="" className="owner-auth-icon" />
          <p className="owner-eyebrow">Owner Portal</p>
          <h2>{mode === "login" ? "С возвращением" : mode === "forgot" ? "Восстановить доступ" : "Новый пароль"}</h2>
          <p className="owner-muted">
            {mode === "login"
              ? "Войдите, чтобы открыть панель объектов."
              : mode === "forgot"
                ? "Отправим безопасную ссылку на email аккаунта."
                : "Придумайте пароль не короче 12 символов с буквами и цифрами."}
          </p>
          {mode !== "reset" ? (
            <label>Email<input required type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} /></label>
          ) : null}
          {mode !== "forgot" ? (
            <label>{mode === "reset" ? "Новый пароль" : "Пароль"}<input required type="password" minLength={mode === "reset" ? 12 : 1} autoComplete={mode === "reset" ? "new-password" : "current-password"} value={password} onChange={(event) => setPassword(event.target.value)} /></label>
          ) : null}
          {error ? <p className="owner-alert danger" role="alert">{error}</p> : null}
          {message ? <p className="owner-alert success" role="status">{message}</p> : null}
          <button className="owner-primary" disabled={busy}>
            {busy ? "Подождите…" : mode === "login" ? "Войти в кабинет" : mode === "forgot" ? "Отправить ссылку" : "Обновить пароль"}
          </button>
          <button type="button" className="owner-link-button" onClick={() => setMode(mode === "login" ? "forgot" : "login")}>
            {mode === "login" ? "Не помню пароль" : "Вернуться ко входу"}
          </button>
        </form>
      </section>
    </main>
  );
}

function DashboardView({ data, onCamp, onChanges }: { data: OwnerDashboard; onCamp: (camp: OwnerCamp) => void; onChanges: () => void }) {
  const firstName = data.owner.display_name.split(" ")[0] || "владелец";
  return (
    <>
      <section className="owner-welcome">
        <div>
          <p className="owner-eyebrow">Обзор объектов</p>
          <h1>Здравствуйте, {firstName}</h1>
          <p>Здесь сразу видно, что происходит с карточками и что требует внимания.</p>
        </div>
        <div className="owner-summary-pill"><Clock3 /><span><b>{data.profile_statistics.pending_changes}</b> ожидают проверки</span></div>
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
                <span className="owner-object-copy"><b>{camp.name}</b><small>{camp.publication_status === "published" ? "Опубликован" : "Не опубликован"} · {camp.pending_changes} на проверке</small></span>
                <ChevronRight />
              </button>
            ))}
            {!data.camps.length ? <p className="owner-empty">С аккаунтом пока не связан ни один объект.</p> : null}
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
          {data.pending_changes.slice(0, 5).map((change) => (
            <div className="owner-change-line" key={change.id}><div><b>{change.camp_name}</b><small>{change.public_number} · {formatDate(change.updated_at)}</small></div><OwnerBadge change={change} /></div>
          ))}
          {!data.pending_changes.length ? <p className="owner-empty">Сейчас нет изменений, ожидающих решения.</p> : null}
        </section> : null}
        <section className="owner-card owner-activity">
          <div className="owner-section-heading"><div><p className="owner-eyebrow">Последние события</p><h2>Активность</h2></div><Activity /></div>
          <div className="owner-timeline">
            {data.activity.slice(0, 7).map((event) => {
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

function ObjectsView({ camps, onCamp }: { camps: OwnerCamp[]; onCamp: (camp: OwnerCamp) => void }) {
  return (
    <section>
      <div className="owner-page-heading"><div><p className="owner-eyebrow">Портфель</p><h1>Мои объекты</h1><p>Заполненность, состояние публикации и ожидающие изменения.</p></div></div>
      <div className="owner-camp-grid">
        {camps.map((camp) => (
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
    </section>
  );
}

function ChangesView({ changes, onOpen }: { changes: OwnerChange[]; onOpen: (change: OwnerChange) => void }) {
  return (
    <section>
      <div className="owner-page-heading"><div><p className="owner-eyebrow">История модерации</p><h1>Изменения</h1><p>Что отправлялось, когда и с каким результатом.</p></div></div>
      <div className="owner-history-list">
        {changes.map((change) => (
          <article className="owner-card" key={change.id}>
            <div className="owner-change-line"><div><h2>{change.camp_name}</h2><small>{change.public_number} · создано {formatDate(change.created_at)}</small></div><OwnerBadge change={change} /></div>
            <p>{change.diff_payload.length} изменённых полей</p>
            {change.moderator_comment ? <div className="owner-moderator-comment"><b>Комментарий модератора</b>{change.moderator_comment}</div> : null}
            <div className="owner-history-meta">
              <span>Отправлено: {formatDate(change.submitted_at)}</span>
              <span>Решение: {formatDate(change.decided_at)}</span>
              {change.moderator_name ? <span>Модератор: {change.moderator_name}</span> : null}
            </div>
            <button className="owner-text-action owner-change-open" onClick={() => onOpen(change)}>
              Открыть эти изменения <ChevronRight />
            </button>
          </article>
        ))}
        {!changes.length ? <p className="owner-empty owner-card">История пока пуста.</p> : null}
      </div>
    </section>
  );
}

function ProfileView({ dashboard, onUpdated }: { dashboard: OwnerDashboard; onUpdated: (owner: OwnerProfile) => void }) {
  const [profile, setProfile] = useState(dashboard.owner);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  async function save(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const result = await ownerApi.updateProfile({
        display_name: profile.display_name,
        company: profile.company,
        phone: profile.phone,
        telegram: profile.telegram,
        whatsapp: profile.whatsapp,
        max: profile.max,
        preferred_contact_type: profile.preferred_contact_type,
      });
      setProfile(result.owner);
      onUpdated(result.owner);
      setMessage("Профиль сохранён");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось сохранить профиль");
    }
  }
  async function savePassword(event: FormEvent) {
    event.preventDefault();
    setError("");
    setMessage("");
    try {
      const result = await ownerApi.changePassword(currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      setMessage(result.message);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось обновить пароль");
    }
  }
  return (
    <section>
      <div className="owner-page-heading"><div><p className="owner-eyebrow">Аккаунт</p><h1>Профиль владельца</h1><p>Контакты и сводка работы с объектами.</p></div></div>
      <div className="owner-profile-grid">
        <div className="owner-profile-stack">
          <form className="owner-card owner-profile-form" onSubmit={save}>
            <h2>Контактные данные</h2>
            <label>Имя<input required value={profile.display_name} onChange={(event) => setProfile({ ...profile, display_name: event.target.value })} /></label>
            <label>Компания<input value={profile.company || ""} onChange={(event) => setProfile({ ...profile, company: event.target.value })} /></label>
            <label>Телефон<input value={profile.phone || ""} onChange={(event) => setProfile({ ...profile, phone: event.target.value })} /></label>
            <label>Telegram<input value={profile.telegram || ""} onChange={(event) => setProfile({ ...profile, telegram: event.target.value })} /></label>
            <label>WhatsApp<input value={profile.whatsapp || ""} onChange={(event) => setProfile({ ...profile, whatsapp: event.target.value })} /></label>
            <label>MAX<input value={profile.max || ""} onChange={(event) => setProfile({ ...profile, max: event.target.value })} /></label>
            <label className="owner-profile-wide">Предпочтительный способ связи
              <select value={profile.preferred_contact_type || "email"} onChange={(event) => setProfile({ ...profile, preferred_contact_type: event.target.value })}>
                <option value="email">Email</option><option value="phone">Телефон</option><option value="telegram">Telegram</option><option value="whatsapp">WhatsApp</option><option value="max">MAX</option>
              </select>
            </label>
            <button className="owner-primary">Сохранить профиль</button>
          </form>
          <form className="owner-card owner-profile-form owner-password-form" onSubmit={savePassword}>
            <h2>Безопасность</h2>
            <label>Текущий пароль<input required type="password" autoComplete="current-password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} /></label>
            <label>Новый пароль<input required type="password" autoComplete="new-password" minLength={12} value={newPassword} onChange={(event) => setNewPassword(event.target.value)} /></label>
            <button className="owner-secondary">Обновить пароль</button>
          </form>
          {error ? <p className="owner-alert danger" role="alert">{error}</p> : null}
          {message ? <p className="owner-alert success" role="status">{message}</p> : null}
        </div>
        <aside className="owner-card owner-profile-summary">
          <h2>Карточка владельца</h2>
          <dl>
            <div><dt>Email</dt><dd>{profile.email}</dd></div>
            <div><dt>Объектов</dt><dd>{dashboard.profile_statistics.objects_count}</dd></div>
            <div><dt>Дата регистрации</dt><dd>{formatDate(profile.created_at, false)}</dd></div>
            <div><dt>Последний вход</dt><dd>{formatDate(profile.last_login)}</dd></div>
            <div><dt>Способ связи</dt><dd>{{ email: "Email", phone: "Телефон", telegram: "Telegram", whatsapp: "WhatsApp", max: "MAX" }[profile.preferred_contact_type || "email"]}</dd></div>
            <div><dt>Статус</dt><dd>{profile.account_status === "active" ? "Активен" : profile.account_status === "suspended" ? "Приостановлен" : "Ожидает активации"}</dd></div>
            <div><dt>Одобрено</dt><dd>{dashboard.profile_statistics.approved_changes}</dd></div>
            <div><dt>Ожидают</dt><dd>{dashboard.profile_statistics.pending_changes}</dd></div>
            <div><dt>Отклонено</dt><dd>{dashboard.profile_statistics.rejected_changes}</dd></div>
          </dl>
        </aside>
      </div>
    </section>
  );
}

function CampDetail({ camp, changeRequestsEnabled, onBack, onReload }: { camp: OwnerCamp; changeRequestsEnabled: boolean; onBack: () => void; onReload: () => void }) {
  type CampDetailData = {
    camp: Record<string, unknown>;
    quality: OwnerCamp["quality"];
    changes: OwnerChange[];
    amenity_catalog: Array<{ id: number; name: string; category: string }>;
  };
  const [detail, setDetail] = useState<CampDetailData | null>(null);
  const [change, setChange] = useState<OwnerChange | null>(null);
  const [proposal, setProposal] = useState<Record<string, unknown>>({});
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    ownerApi.camp(camp.id).then(setDetail).catch((reason) => setError(reason instanceof Error ? reason.message : "Ошибка загрузки"));
  }, [camp.id]);

  const diff = useMemo<ChangeDiff[]>(() => {
    if (!detail) return [];
    const items = change?.diff_payload?.length
      ? [...change.diff_payload]
      : Object.entries(proposal)
        .filter(([key, value]) => detail.camp[key] !== value)
        .map(([field, after]) => ({
          field,
          label: { name: "Название", short_description: "Краткое описание", description: "Описание", min_price: "Минимальная цена", seasonality: "Сезонность", working_hours: "Режим работы", surroundings: "Окрестности", contacts: "Контакты", amenities: "Удобства", rooms: "Варианты размещения", video_urls: "Видео", request_publication: "Повторная публикация" }[field] || field,
          before: detail.camp[field],
          after,
        }));
    if (change?.staged_media?.length && !items.some((item) => item.field === "media")) {
      const added = change.staged_media.filter((item) => item.action !== "remove").length;
      const removed = change.staged_media.filter((item) => item.action === "remove").length;
      items.push({
        field: "media",
        label: "Фото",
        before: removed ? `Будет удалено: ${removed}` : "Без удалений",
        after: added ? `Будет добавлено: ${added}` : "Без новых фотографий",
      });
    }
    return items;
  }, [change, detail, proposal]);

  function currentList<T>(key: string): T[] {
    const value = proposal[key] ?? detail?.camp[key];
    return Array.isArray(value) ? value as T[] : [];
  }

  async function beginEdit() {
    try {
      const result = await ownerApi.createChange(camp.id);
      setChange(result.change);
      setProposal(result.change.proposed_payload || {});
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось создать черновик");
    }
  }

  async function saveAndPreview() {
    if (!change) return;
    try {
      const result = await ownerApi.saveChange(change.id, change.content_version, proposal);
      setChange(result.change);
      setMessage("Черновик сохранён. Проверьте сравнение перед отправкой.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось сохранить");
    }
  }

  async function submit() {
    if (!change) return;
    try {
      const result = await ownerApi.submitChange(change.id);
      setChange(result.change);
      setMessage("Изменения отправлены на проверку");
      onReload();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось отправить");
    }
  }

  async function requestPublication() {
    try {
      const draft = await ownerApi.createChange(camp.id);
      const saved = await ownerApi.saveChange(
        draft.change.id,
        draft.change.content_version,
        { ...draft.change.proposed_payload, request_publication: true },
      );
      setChange(saved.change);
      setProposal(saved.change.proposed_payload);
      setMessage("Запрос на повторную публикацию подготовлен. Проверьте и отправьте его.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось подготовить запрос");
    }
  }

  function updateContact(contactType: string, value: string) {
    const contacts = currentList<Record<string, unknown>>("contacts").filter((item) => String(item.contact_type) !== contactType);
    if (value.trim()) {
      contacts.push({
        contact_type: contactType,
        label: { phone: "Телефон", telegram: "Telegram", whatsapp: "WhatsApp", max: "MAX" }[contactType],
        value: value.trim(),
        is_public: true,
        sort_order: contacts.length * 10,
      });
    }
    setProposal({ ...proposal, contacts });
  }

  function contactValue(contactType: string) {
    return String(currentList<Record<string, unknown>>("contacts").find((item) => String(item.contact_type) === contactType)?.value || "");
  }

  function toggleAmenity(amenityId: number) {
    const amenities = currentList<Record<string, unknown>>("amenities");
    const present = amenities.some((item) => Number(item.amenity_id) === amenityId);
    setProposal({
      ...proposal,
      amenities: present
        ? amenities.filter((item) => Number(item.amenity_id) !== amenityId)
        : [...amenities, { amenity_id: amenityId, value: null }],
    });
  }

  function updateRoom(index: number, key: string, value: unknown) {
    const rooms = currentList<Record<string, unknown>>("rooms").map((room) => ({ ...room }));
    rooms[index] = { ...rooms[index], [key]: value };
    setProposal({ ...proposal, rooms });
  }

  function removeRoom(index: number) {
    setProposal({
      ...proposal,
      rooms: currentList<Record<string, unknown>>("rooms").filter((_, itemIndex) => itemIndex !== index),
    });
  }

  async function uploadPhoto(file?: File) {
    if (!file || !change) return;
    const body = new FormData();
    body.set("file", file);
    body.set("scope", "place");
    body.set("sort_order", String(change.staged_media?.length || 0));
    body.set("is_cover", String(!change.staged_media?.length));
    try {
      await ownerApi.uploadMedia(change.id, body);
      const refreshed = await ownerApi.getChange(change.id);
      setChange(refreshed.change);
      setMessage("Фотография добавлена в предложенные изменения");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось загрузить фотографию");
    }
  }

  async function removePublishedPhoto(mediaId: number) {
    if (!change) return;
    try {
      await ownerApi.removePublishedMedia(change.id, mediaId);
      const refreshed = await ownerApi.getChange(change.id);
      setChange(refreshed.change);
      setMessage("Удаление фотографии добавлено в предложенные изменения");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось изменить галерею");
    }
  }

  async function removeStagedPhoto(mediaId: number) {
    if (!change) return;
    try {
      await ownerApi.deleteStagedMedia(change.id, mediaId);
      const refreshed = await ownerApi.getChange(change.id);
      setChange(refreshed.change);
      setMessage("Новая фотография удалена из черновика");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось изменить галерею");
    }
  }

  if (!detail) return <p className="owner-card owner-empty">{error || "Открываем карточку…"}</p>;
  return (
    <section>
      <button className="owner-back" onClick={onBack}><ArrowLeft /> К списку объектов</button>
      <div className="owner-detail-heading">
        <div><p className="owner-eyebrow">Управление объектом</p><h1>{camp.name}</h1><p>{detail.camp.address ? String(detail.camp.address) : "Адрес не указан"}</p></div>
        {!change && changeRequestsEnabled ? <div className="owner-heading-actions"><button className="owner-primary" onClick={beginEdit}><PencilLine /> Предложить изменения</button>{camp.publication_status !== "published" ? <button className="owner-secondary" onClick={requestPublication}>Запросить публикацию</button> : null}</div> : change && changeRequestsEnabled ? <OwnerBadge change={change} /> : null}
      </div>
      {error ? <p className="owner-alert danger">{error}</p> : null}
      {message ? <p className="owner-alert success">{message}</p> : null}
      <div className="owner-detail-grid">
        <section className="owner-card owner-quality-panel">
          <QualityRing score={detail.quality.score} />
          <div><h2>Карточка заполнена на {detail.quality.score}%</h2><div className="owner-progress"><span style={{ width: `${detail.quality.score}%` }} /></div></div>
          <ul>{detail.quality.checklist.map((item) => <li key={item.key} className={item.complete ? "complete" : ""}>{item.complete ? <Check /> : <X />}{item.label}</li>)}</ul>
        </section>
        <section className="owner-card owner-health-panel"><h2>Состояние объекта</h2>{detail.quality.health.map((item) => <div key={item.key} className={item.level}><span />{item.label}</div>)}</section>
      </div>
      {changeRequestsEnabled && change && ["draft", "needs_changes", "withdrawn"].includes(change.status) ? (
        <div className="owner-editor-grid">
          <section className="owner-card owner-editor">
            <div className="owner-section-heading"><div><p className="owner-eyebrow">Редактор</p><h2>Данные карточки</h2></div></div>
            {[["name", "Название"], ["short_description", "Краткое описание"], ["seasonality", "Сезонность"], ["working_hours", "Режим работы"], ["surroundings", "Описание окрестностей"]].map(([key, label]) => <label key={key}>{label}<input value={String(proposal[key] ?? detail.camp[key] ?? "")} onChange={(event) => setProposal({ ...proposal, [key]: event.target.value })} /></label>)}
            <label>Подробное описание<textarea rows={8} value={String(proposal.description ?? detail.camp.description ?? "")} onChange={(event) => setProposal({ ...proposal, description: event.target.value })} /></label>
            <label>Минимальная цена<input type="number" min="0" value={String(proposal.min_price ?? detail.camp.min_price ?? "")} onChange={(event) => setProposal({ ...proposal, min_price: event.target.value ? Number(event.target.value) : null })} /></label>
            <fieldset className="owner-editor-section">
              <legend>Публичные контакты</legend>
              <label>Телефон<input placeholder="+7 999 000-00-00" value={contactValue("phone")} onChange={(event) => updateContact("phone", event.target.value)} /></label>
              <label>Telegram<input placeholder="https://t.me/..." value={contactValue("telegram")} onChange={(event) => updateContact("telegram", event.target.value)} /></label>
              <label>WhatsApp<input placeholder="https://wa.me/..." value={contactValue("whatsapp")} onChange={(event) => updateContact("whatsapp", event.target.value)} /></label>
              <label>MAX<input placeholder="https://max.ru/..." value={contactValue("max")} onChange={(event) => updateContact("max", event.target.value)} /></label>
            </fieldset>
            <fieldset className="owner-editor-section">
              <legend>Удобства</legend>
              <div className="owner-amenity-grid">{detail.amenity_catalog.map((amenity) => {
                const checked = currentList<Record<string, unknown>>("amenities").some((item) => Number(item.amenity_id) === amenity.id);
                return <label key={amenity.id} className={checked ? "selected" : ""}><input type="checkbox" checked={checked} onChange={() => toggleAmenity(amenity.id)} />{amenity.name}</label>;
              })}</div>
            </fieldset>
            <fieldset className="owner-editor-section">
              <legend>Варианты размещения</legend>
              <div className="owner-room-list">
                {currentList<Record<string, unknown>>("rooms").map((room, index) => <div key={String(room.id || room.client_id || index)} className="owner-room-row"><label>Название<input value={String(room.name || "")} onChange={(event) => updateRoom(index, "name", event.target.value)} /></label><label>Цена<input type="number" min="0" value={String(room.price || "")} onChange={(event) => updateRoom(index, "price", Number(event.target.value) || null)} /></label><label className="wide">Описание<textarea rows={3} value={String(room.description || "")} onChange={(event) => updateRoom(index, "description", event.target.value)} /></label><button type="button" className="owner-room-remove" onClick={() => removeRoom(index)}><X /> Удалить вариант</button></div>)}
                <button type="button" className="owner-secondary" onClick={() => setProposal({ ...proposal, rooms: [...currentList<Record<string, unknown>>("rooms"), { client_id: crypto.randomUUID(), name: "Новый вариант", description: "", price: null }] })}>Добавить вариант</button>
              </div>
            </fieldset>
            <fieldset className="owner-editor-section">
              <legend>Фото и видео</legend>
              <div className="owner-media-strip">
                {currentList<Record<string, unknown>>("media").map((media) => {
                  const marked = change.staged_media?.some((item) => item.action === "remove" && item.target_media_id === Number(media.id));
                  return (
                    <div key={String(media.id)} className={marked ? "marked" : ""}>
                      <img src={String(media.url)} alt="" />
                      <button type="button" disabled={marked} onClick={() => void removePublishedPhoto(Number(media.id))}>
                        {marked ? "Удалится" : "Убрать"}
                      </button>
                    </div>
                  );
                })}
                {change.staged_media?.filter((media) => media.action !== "remove" && media.public_preview_url).map((media) => (
                  <div key={`staged-${media.id}`}>
                    <img src={`${media.public_preview_url}?thumbnail=1`} alt="Новое фото" />
                    <button type="button" onClick={() => void removeStagedPhoto(media.id)}>Отменить</button>
                  </div>
                ))}
              </div>
              <label className="owner-upload">Добавить фотографию<input type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => void uploadPhoto(event.target.files?.[0])} /></label>
              <label>Ссылка на видео<input placeholder="YouTube, Rutube, VK Video" value={String(currentList<string>("video_urls")[0] || "")} onChange={(event) => setProposal({ ...proposal, video_urls: event.target.value ? [event.target.value] : [] })} /></label>
            </fieldset>
            <div className="owner-editor-actions"><button className="owner-secondary" onClick={saveAndPreview}>Сохранить черновик</button><button className="owner-primary" disabled={!diff.length} onClick={submit}><Send /> Отправить на проверку</button></div>
          </section>
          <DiffViewer items={diff} />
        </div>
      ) : null}
      {camp.publication_status === "published" ? <section className="owner-card owner-danger-zone"><div><h2>Снять объект с публикации</h2><p>Карточка исчезнет из каталога сразу. Повторная публикация потребует проверки.</p></div><button onClick={async () => { if (window.confirm("Снять объект с публикации?")) { await ownerApi.unpublish(camp.id); onReload(); } }}>Снять с публикации</button></section> : null}
    </section>
  );
}

export default function OwnerPortal() {
  const [auth, setAuth] = useState<"loading" | "authenticated" | "anonymous">("loading");
  const [owner, setOwner] = useState<OwnerProfile | null>(null);
  const [dashboard, setDashboard] = useState<OwnerDashboard | null>(null);
  const [view, setView] = useState<View>("dashboard");
  const [selectedCamp, setSelectedCamp] = useState<OwnerCamp | null>(null);
  const [mobileNav, setMobileNav] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const previous = document.title;
    document.title = "Кабинет владельца — Туристика";
    return () => { document.title = previous; };
  }, []);

  const load = () => ownerApi.dashboard().then((payload) => { setDashboard(payload); setOwner(payload.owner); }).catch((reason) => setError(reason instanceof Error ? reason.message : "Не удалось загрузить кабинет"));
  useEffect(() => {
    ownerApi.session()
      .then((payload) => { setOwner(payload.owner); setAuth("authenticated"); return load(); })
      .catch(() => setAuth("anonymous"));
  }, []);

  if (auth === "loading") return <div className="owner-loading"><img src="/static/brand/turistika-icon.svg" width="160" height="160" alt="" /><span>Открываем кабинет…</span></div>;
  if (auth === "anonymous") return <LoginScreen onLogin={(nextOwner) => { setOwner(nextOwner); setAuth("authenticated"); void load(); }} />;
  if (!dashboard || !owner) return <div className="owner-loading">{error || "Загружаем данные…"}</div>;

  const nav: Array<{ key: View; label: string; icon: typeof LayoutDashboard }> = [
    { key: "dashboard", label: "Главная", icon: LayoutDashboard },
    { key: "objects", label: "Мои объекты", icon: Building2 },
    ...(dashboard.features.change_requests ? [{ key: "changes" as View, label: "Изменения", icon: FileClock }] : []),
    { key: "profile", label: "Профиль владельца", icon: UserRound },
  ];
  function navigate(next: View) { setSelectedCamp(null); setView(next); setMobileNav(false); }

  return (
    <div className="owner-shell">
      <aside className={`owner-sidebar ${mobileNav ? "open" : ""}`}>
        <a className="owner-logo" href="/owner"><img src="/static/brand/turistika-logo-horizontal-dark.svg" width="720" height="180" alt="Туристика" /></a>
        <p className="owner-product-label">Кабинет владельца</p>
        <nav>{nav.map(({ key, label, icon: Icon }) => <button key={key} className={view === key && !selectedCamp ? "active" : ""} onClick={() => navigate(key)}><Icon />{label}{key === "changes" && dashboard.profile_statistics.pending_changes ? <span>{dashboard.profile_statistics.pending_changes}</span> : null}</button>)}</nav>
        <div className="owner-sidebar-profile"><div>{owner.display_name.slice(0, 1).toUpperCase()}</div><span><b>{owner.display_name}</b><small>{owner.company || owner.email}</small></span></div>
        <button className="owner-logout" onClick={async () => { await ownerApi.logout(); setAuth("anonymous"); setDashboard(null); }}><LogOut /> Выйти</button>
      </aside>
      <div className="owner-main">
        <header className="owner-mobile-header"><img src="/static/brand/turistika-logo-horizontal.svg" width="720" height="180" alt="Туристика" /><button aria-label={mobileNav ? "Закрыть меню" : "Открыть меню"} onClick={() => setMobileNav(!mobileNav)}>{mobileNav ? <X /> : <Menu />}</button></header>
        <main>
          {selectedCamp ? <CampDetail camp={selectedCamp} changeRequestsEnabled={dashboard.features.change_requests} onBack={() => setSelectedCamp(null)} onReload={load} /> : null}
          {!selectedCamp && view === "dashboard" ? <DashboardView data={dashboard} onCamp={setSelectedCamp} onChanges={() => setView("changes")} /> : null}
          {!selectedCamp && view === "objects" ? <ObjectsView camps={dashboard.camps} onCamp={setSelectedCamp} /> : null}
          {!selectedCamp && view === "changes" ? <ChangesView changes={dashboard.changes} onOpen={(change) => {
            const camp = dashboard.camps.find((item) => item.id === change.camp_id);
            if (camp) setSelectedCamp(camp);
          }} /> : null}
          {!selectedCamp && view === "profile" ? <ProfileView dashboard={dashboard} onUpdated={(next) => { setOwner(next); setDashboard({ ...dashboard, owner: next }); }} /> : null}
        </main>
      </div>
    </div>
  );
}
