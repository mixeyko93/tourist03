import { Check, Clock3, RefreshCcw, ShieldCheck, UserRound, X } from "lucide-react";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { DiffViewer } from "../../../owner/DiffViewer";
import { apiRequest, type OwnerChange } from "../../../owner/api";
import { PageMotion } from "../../components/PageMotion";

type OwnerAccount = {
  id: number;
  email: string;
  display_name: string;
  company?: string | null;
  is_active: boolean;
  account_status: string;
  camps: Array<{ camp_id: number; camp_name: string; role_key: string; is_primary: boolean }>;
};

const statusLabels: Record<string, string> = {
  draft: "Черновик",
  submitted: "Отправлено",
  in_review: "На проверке",
  needs_changes: "Нужны изменения",
  approved: "Одобрено",
  applied: "Опубликовано",
  rejected: "Отклонено",
  withdrawn: "Отозвано",
  archived: "В архиве",
};

const roleLabels: Record<string, string> = {
  primary_owner: "Основной владелец",
  owner: "Владелец",
  representative: "Представитель",
  manager: "Управляющий",
  editor: "Редактор",
  viewer: "Только просмотр",
};

function formatDate(value?: string | null) {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "—" : parsed.toLocaleString("ru-RU");
}

export default function AdminOwnerChangesPage() {
  const [items, setItems] = useState<OwnerChange[]>([]);
  const [owners, setOwners] = useState<OwnerAccount[]>([]);
  const [selected, setSelected] = useState<OwnerChange | null>(null);
  const [tab, setTab] = useState<"changes" | "owners">("changes");
  const [filters, setFilters] = useState({
    status: "", campId: "", ownerId: "", region: "", dateFrom: "", dateTo: "",
  });
  const [newOwner, setNewOwner] = useState({
    email: "", password: "", displayName: "", company: "",
  });
  const [campLinks, setCampLinks] = useState<Record<number, { campId: string; roleKey: string }>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function load() {
    setError("");
    const query = new URLSearchParams();
    if (filters.status) query.set("status", filters.status);
    if (filters.campId) query.set("camp_id", filters.campId);
    if (filters.ownerId) query.set("owner_id", filters.ownerId);
    if (filters.region.trim()) query.set("region", filters.region.trim());
    if (filters.dateFrom) query.set("date_from", filters.dateFrom);
    if (filters.dateTo) query.set("date_to", filters.dateTo);
    const [changeResponse, ownerResponse] = await Promise.all([
      apiRequest<{ changes: OwnerChange[] }>(`/api/superadmin/owner-changes${query.size ? `?${query}` : ""}`),
      apiRequest<{ owners: OwnerAccount[] }>("/api/superadmin/owners"),
    ]);
    setItems(changeResponse.changes);
    setOwners(ownerResponse.owners);
    if (selected) {
      const fresh = changeResponse.changes.find((item) => item.id === selected.id);
      if (fresh) setSelected(fresh);
    } else if (changeResponse.changes[0]) {
      await openChange(changeResponse.changes[0].id);
    }
  }

  async function openChange(id: number) {
    try {
      const response = await apiRequest<{ change: OwnerChange }>(`/api/superadmin/owner-changes/${id}`);
      setSelected(response.change);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось открыть изменения");
    }
  }

  useEffect(() => {
    void load().catch((reason) => setError(reason instanceof Error ? reason.message : "Ошибка загрузки"));
  }, []);

  async function decision(status: "in_review" | "needs_changes" | "approved" | "rejected" | "archived") {
    if (!selected) return;
    const needsComment = status === "needs_changes" || status === "rejected";
    const comment = needsComment ? window.prompt("Комментарий владельцу", "")?.trim() : "";
    if (needsComment && !comment) return;
    setBusy(true);
    setError("");
    try {
      const result = await apiRequest<{ change: OwnerChange }>(
        `/api/superadmin/owner-changes/${selected.id}/decision`,
        {
          method: "POST",
          body: JSON.stringify({ status, comment: comment || null }),
        },
      );
      setSelected(result.change);
      setMessage(`Статус: ${statusLabels[result.change.status]}`);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось сохранить решение");
    } finally {
      setBusy(false);
    }
  }

  async function applyApproved() {
    if (!selected) return;
    setBusy(true);
    try {
      const result = await apiRequest<{ change: OwnerChange; applied: boolean }>(
        `/api/superadmin/owner-changes/${selected.id}/apply`,
        {
          method: "POST",
          body: JSON.stringify({ idempotency_key: crypto.randomUUID() }),
        },
      );
      setSelected(result.change);
      setMessage(result.applied ? "Изменения опубликованы" : "Изменения уже были опубликованы");
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось применить изменения");
    } finally {
      setBusy(false);
    }
  }

  async function toggleOwner(owner: OwnerAccount) {
    try {
      await apiRequest(`/api/superadmin/owners/${owner.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          is_active: !owner.is_active,
          account_status: owner.is_active ? "suspended" : "active",
        }),
      });
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось изменить аккаунт");
    }
  }

  async function createOwner(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await apiRequest("/api/superadmin/owners", {
        method: "POST",
        body: JSON.stringify({
          email: newOwner.email,
          password: newOwner.password,
          display_name: newOwner.displayName,
          company: newOwner.company || null,
        }),
      });
      setNewOwner({ email: "", password: "", displayName: "", company: "" });
      setMessage("Аккаунт владельца создан, приветствие добавлено в очередь отправки");
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось создать аккаунт");
    } finally {
      setBusy(false);
    }
  }

  async function linkCamp(owner: OwnerAccount) {
    const form = campLinks[owner.id] || { campId: "", roleKey: "owner" };
    if (!form.campId) return;
    setBusy(true);
    setError("");
    try {
      await apiRequest(`/api/superadmin/owners/${owner.id}/camps`, {
        method: "POST",
        body: JSON.stringify({
          camp_id: Number(form.campId),
          role_key: form.roleKey,
          is_primary: form.roleKey === "primary_owner",
        }),
      });
      setCampLinks({ ...campLinks, [owner.id]: { campId: "", roleKey: "owner" } });
      setMessage(`Объект связан с аккаунтом ${owner.display_name}`);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось связать объект");
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageMotion className="space-y-6" isReady>
      <section className="rounded-3xl border border-border bg-card/80 p-5 shadow-sm sm:p-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Owner Portal</p>
            <h2 className="mt-2 text-3xl font-semibold tracking-[-0.05em]">Изменения владельцев</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">Единый Diff Viewer, понятные решения и отдельная транзакционная публикация после одобрения.</p>
          </div>
          <button type="button" className="admin-button gap-2" onClick={() => void load()}><RefreshCcw className="h-4 w-4" />Обновить</button>
        </div>
        <div className="mt-5 flex flex-wrap gap-2">
          <button className={tab === "changes" ? "admin-primary-button" : "admin-button"} onClick={() => setTab("changes")}><ShieldCheck className="h-4 w-4" />Изменения</button>
          <button className={tab === "owners" ? "admin-primary-button" : "admin-button"} onClick={() => setTab("owners")}><UserRound className="h-4 w-4" />Владельцы</button>
        </div>
      </section>
      {error ? <div role="alert" className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">{error}</div> : null}
      {message ? <div role="status" className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300">{message}</div> : null}

      {tab === "owners" ? (
        <div className="space-y-5">
          <form className="rounded-3xl border border-border bg-card/75 p-5" onSubmit={createOwner}>
            <div>
              <h3 className="font-semibold">Новый аккаунт владельца</h3>
              <p className="mt-1 text-sm text-muted-foreground">После создания приветствие попадёт в существующую очередь уведомлений.</p>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <label className="text-xs text-muted-foreground">Имя<input required className="admin-input mt-1" value={newOwner.displayName} onChange={(event) => setNewOwner({ ...newOwner, displayName: event.target.value })} /></label>
              <label className="text-xs text-muted-foreground">Компания<input className="admin-input mt-1" value={newOwner.company} onChange={(event) => setNewOwner({ ...newOwner, company: event.target.value })} /></label>
              <label className="text-xs text-muted-foreground">Email<input required type="email" className="admin-input mt-1" value={newOwner.email} onChange={(event) => setNewOwner({ ...newOwner, email: event.target.value })} /></label>
              <label className="text-xs text-muted-foreground">Временный пароль<input required type="password" minLength={12} className="admin-input mt-1" value={newOwner.password} onChange={(event) => setNewOwner({ ...newOwner, password: event.target.value })} /></label>
            </div>
            <button disabled={busy} className="admin-primary-button mt-4">Создать аккаунт</button>
          </form>
          <section className="grid gap-3 lg:grid-cols-2">
            {owners.map((owner) => {
              const link = campLinks[owner.id] || { campId: "", roleKey: "owner" };
              return (
              <article key={owner.id} className="rounded-3xl border border-border bg-card/75 p-5">
              <div className="flex items-start justify-between gap-4">
                <div><h3 className="font-semibold">{owner.display_name}</h3><p className="mt-1 text-sm text-muted-foreground">{owner.company || owner.email}</p></div>
                <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${owner.is_active ? "bg-emerald-500/10 text-emerald-300" : "bg-rose-500/10 text-rose-300"}`}>{owner.is_active ? "Активен" : "Приостановлен"}</span>
              </div>
              <div className="mt-4 space-y-2 text-sm text-muted-foreground">{owner.camps.map((camp) => <p key={camp.camp_id}>{camp.camp_name} · {roleLabels[camp.role_key] || camp.role_key}</p>)}</div>
              {!owner.camps.length ? <p className="mt-4 text-sm text-muted-foreground">Объекты пока не связаны.</p> : null}
              <div className="mt-4 grid grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)] gap-2">
                <input aria-label={`ID объекта для ${owner.display_name}`} type="number" min="1" placeholder="ID объекта" className="admin-input" value={link.campId} onChange={(event) => setCampLinks({ ...campLinks, [owner.id]: { ...link, campId: event.target.value } })} />
                <select aria-label={`Роль ${owner.display_name}`} className="admin-input" value={link.roleKey} onChange={(event) => setCampLinks({ ...campLinks, [owner.id]: { ...link, roleKey: event.target.value } })}>
                  {Object.entries(roleLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
                </select>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <button disabled={busy || !link.campId} className="admin-button" onClick={() => void linkCamp(owner)}>Связать объект</button>
                <button className="admin-button" onClick={() => void toggleOwner(owner)}>{owner.is_active ? "Приостановить доступ" : "Восстановить доступ"}</button>
              </div>
            </article>
            );})}
          </section>
        </div>
      ) : (
        <>
          <div className="grid gap-2 rounded-3xl border border-border bg-card/60 p-4 md:grid-cols-2 xl:grid-cols-7">
            <select aria-label="Статус изменений" className="admin-input" value={filters.status} onChange={(event) => setFilters({ ...filters, status: event.target.value })}>
              <option value="">Все статусы</option>
              {Object.entries(statusLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
            </select>
            <input aria-label="ID объекта" type="number" min="1" placeholder="ID объекта" className="admin-input" value={filters.campId} onChange={(event) => setFilters({ ...filters, campId: event.target.value })} />
            <input aria-label="ID владельца" type="number" min="1" placeholder="ID владельца" className="admin-input" value={filters.ownerId} onChange={(event) => setFilters({ ...filters, ownerId: event.target.value })} />
            <input aria-label="Регион" placeholder="Регион" className="admin-input" value={filters.region} onChange={(event) => setFilters({ ...filters, region: event.target.value })} />
            <input aria-label="Дата с" type="date" className="admin-input" value={filters.dateFrom} onChange={(event) => setFilters({ ...filters, dateFrom: event.target.value })} />
            <input aria-label="Дата по" type="date" className="admin-input" value={filters.dateTo} onChange={(event) => setFilters({ ...filters, dateTo: event.target.value })} />
            <button className="admin-primary-button justify-center" onClick={() => void load()}>Применить</button>
          </div>
          <div className="grid min-w-0 gap-5 xl:grid-cols-[360px_minmax(0,1fr)]">
            <aside className="max-h-[calc(100vh-190px)] space-y-2 overflow-auto rounded-3xl border border-border bg-card/70 p-3 xl:sticky xl:top-6">
              {items.map((item) => (
                <button key={item.id} onClick={() => void openChange(item.id)} className={`w-full rounded-2xl border p-4 text-left ${selected?.id === item.id ? "border-blue-500/60 bg-blue-500/10" : "border-border bg-background/55 hover:bg-accent"}`}>
                  <div className="flex items-start justify-between gap-2"><b className="text-sm">{item.camp_name}</b><span className="rounded-full bg-background px-2 py-1 text-[10px] text-muted-foreground">{statusLabels[item.status]}</span></div>
                  <p className="mt-2 text-xs text-muted-foreground">{item.public_number}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{item.diff_count ?? item.diff_payload?.length ?? 0} полей · {formatDate(item.updated_at)}</p>
                </button>
              ))}
              {!items.length ? <p className="p-4 text-sm text-muted-foreground">По выбранным фильтрам изменений нет.</p> : null}
            </aside>
            <main className="min-w-0 space-y-5">
              {selected ? (
                <>
                  <section className="rounded-3xl border border-border bg-card/80 p-5 sm:p-6">
                    <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                      <div><h2 className="text-2xl font-semibold">{selected.camp_name}</h2><p className="mt-2 text-sm text-muted-foreground">{selected.public_number} · {statusLabels[selected.status]}</p></div>
                      <div className="flex flex-wrap gap-2">
                        {selected.status === "submitted" ? <button disabled={busy} className="admin-button gap-2" onClick={() => void decision("in_review")}><Clock3 className="h-4 w-4" />Взять на проверку</button> : null}
                        {selected.status === "in_review" ? <>
                          <button disabled={busy} className="admin-button gap-2" onClick={() => void decision("needs_changes")}><RefreshCcw className="h-4 w-4" />Уточнить</button>
                          <button disabled={busy} className="admin-button gap-2" onClick={() => void decision("rejected")}><X className="h-4 w-4" />Отклонить</button>
                          <button disabled={busy} className="admin-primary-button gap-2" onClick={() => void decision("approved")}><Check className="h-4 w-4" />Одобрить</button>
                        </> : null}
                        {selected.status === "approved" ? <button disabled={busy} className="admin-primary-button gap-2" onClick={() => void applyApproved()}><ShieldCheck className="h-4 w-4" />Опубликовать изменения</button> : null}
                      </div>
                    </div>
                    {selected.moderator_comment ? <div className="mt-4 rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-200">{selected.moderator_comment}</div> : null}
                  </section>
                  <DiffViewer items={selected.diff_payload || []} title="Сравнение для модератора" />
                  <section className="rounded-3xl border border-border bg-card/80 p-5">
                    <h3 className="font-semibold">История решения</h3>
                    <div className="mt-4 space-y-3">{selected.history?.map((event) => <div key={event.id} className="flex justify-between gap-4 border-t border-border pt-3 text-sm"><span>{event.summary}{event.comment ? ` · ${event.comment}` : ""}</span><time className="text-muted-foreground">{formatDate(event.created_at)}</time></div>)}</div>
                  </section>
                </>
              ) : <p className="rounded-3xl border border-border bg-card/70 p-8 text-sm text-muted-foreground">Выберите изменения слева.</p>}
            </main>
          </div>
        </>
      )}
    </PageMotion>
  );
}
