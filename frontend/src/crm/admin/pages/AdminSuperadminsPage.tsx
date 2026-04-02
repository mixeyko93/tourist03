import { Check, PencilLine, Plus, RefreshCcw, RotateCcw, Shield, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { PageMotion } from "../../components/PageMotion";
import { AdminCard } from "../components/AdminCard";
import { AdminField } from "../components/AdminField";
import { AdminModal } from "../components/AdminModal";
import { AdminStatusBadge } from "../components/AdminStatusBadge";
import {
  archiveRootSuperadminAccount,
  createRootSuperadminAccount,
  fetchRootSuperadminAccounts,
  restoreRootSuperadminAccount,
  updateRootSuperadminAccount,
  type SuperadminRootAccount,
} from "../session";

type RootDraft = {
  id: number | null;
  login: string;
  displayName: string;
  phone: string;
  password: string;
  isActive: boolean;
  isRoot: boolean;
};

function createDraft(account: SuperadminRootAccount | null): RootDraft {
  if (!account) {
    return {
      id: null,
      login: "",
      displayName: "",
      phone: "",
      password: "",
      isActive: true,
      isRoot: false,
    };
  }
  return {
    id: account.id,
    login: account.login,
    displayName: account.display_name,
    phone: account.phone || "",
    password: "",
    isActive: account.is_active,
    isRoot: account.is_root,
  };
}

function formatDateTime(value?: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleString("ru-RU");
}

export default function AdminSuperadminsPage() {
  const [items, setItems] = useState<SuperadminRootAccount[]>([]);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [editingId, setEditingId] = useState<number | "new" | null>(null);
  const [draft, setDraft] = useState<RootDraft>(() => createDraft(null));
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const current = typeof editingId === "number" ? items.find((item) => item.id === editingId) ?? null : null;
    setDraft(createDraft(current));
  }, [editingId, items]);

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);
    setErrorMessage("");
    fetchRootSuperadminAccounts({ includeArchived, signal: controller.signal })
      .then((accounts) => setItems(accounts))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setItems([]);
        setErrorMessage(error instanceof Error ? error.message : "Не удалось загрузить superadmin-учётки");
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      });
    return () => controller.abort();
  }, [includeArchived, reloadKey]);

  async function handleSave() {
    try {
      setIsSaving(true);
      setErrorMessage("");
      setSuccessMessage("");
      if (!draft.login.trim()) throw new Error("Укажите логин");
      if (!draft.displayName.trim()) throw new Error("Укажите имя суперадмина");
      if (!draft.id && !draft.password.trim()) throw new Error("Для новой учётной записи требуется пароль");

      const payload = {
        login: draft.login.trim(),
        display_name: draft.displayName.trim(),
        phone: draft.phone.trim() || undefined,
        password: draft.password.trim() || undefined,
        is_active: draft.isActive,
        is_root: draft.isRoot,
      };

      if (draft.id) {
        await updateRootSuperadminAccount(draft.id, payload);
        setSuccessMessage("Учётка суперадмина обновлена.");
      } else {
        await createRootSuperadminAccount(payload);
        setSuccessMessage("Учётка суперадмина создана.");
      }
      setEditingId(null);
      setReloadKey((value) => value + 1);
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : "Не удалось сохранить учётку суперадмина");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleArchive(account: SuperadminRootAccount) {
    if (!window.confirm(`Архивировать superadmin "${account.display_name}"?`)) return;
    try {
      setBusyId(account.id);
      setErrorMessage("");
      setSuccessMessage("");
      await archiveRootSuperadminAccount(account.id);
      setSuccessMessage("Учётка суперадмина архивирована.");
      setReloadKey((value) => value + 1);
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : "Не удалось архивировать superadmin");
    } finally {
      setBusyId(null);
    }
  }

  async function handleRestore(account: SuperadminRootAccount) {
    try {
      setBusyId(account.id);
      setErrorMessage("");
      setSuccessMessage("");
      await restoreRootSuperadminAccount(account.id);
      setSuccessMessage("Учётка суперадмина восстановлена.");
      setReloadKey((value) => value + 1);
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : "Не удалось восстановить superadmin");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <PageMotion className="space-y-6">
      <AdminCard className="overflow-hidden">
        <div className="flex flex-col gap-4 border-b border-border px-5 py-5 sm:px-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Root-only раздел</p>
            <h2 className="text-2xl font-semibold tracking-[-0.04em] text-foreground">Учётки суперадминов</h2>
            <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
              Создание, изменение, архивирование и контроль root-доступов к системе Tourist_03.
            </p>
          </div>

          <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
            <button type="button" className="admin-button gap-2" onClick={() => setReloadKey((value) => value + 1)}>
              <RefreshCcw className="h-4 w-4" />
              Обновить
            </button>
            <button type="button" className="admin-button gap-2" onClick={() => setIncludeArchived((value) => !value)}>
              <RotateCcw className="h-4 w-4" />
              {includeArchived ? "Скрыть архив" : "Показать архив"}
            </button>
            <button type="button" className="admin-primary-button w-full gap-2 sm:w-auto" onClick={() => setEditingId("new")}>
              <Plus className="h-4 w-4" />
              Создать superadmin
            </button>
          </div>
        </div>

        {errorMessage ? <div className="border-b border-border bg-rose-500/10 px-5 py-4 text-sm text-rose-300 sm:px-6">{errorMessage}</div> : null}
        {successMessage ? (
          <div className="border-b border-border bg-emerald-500/10 px-5 py-4 text-sm text-emerald-300 sm:px-6">{successMessage}</div>
        ) : null}

        <div className="admin-table-shell">
          <table className="admin-table min-w-[980px]">
            <thead>
              <tr>
                <th>ID</th>
                <th>Логин</th>
                <th>Имя</th>
                <th>Телефон</th>
                <th>Роль</th>
                <th>Статус</th>
                <th>Создана</th>
                <th className="text-right">Действия</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={8}>Загружаем superadmin-учётки…</td>
                </tr>
              ) : items.length ? (
                items.map((item) => (
                  <tr key={item.id}>
                    <td>#{item.id}</td>
                    <td className="crm-copy-safe font-medium text-foreground">{item.login}</td>
                    <td>{item.display_name}</td>
                    <td>{item.phone || "—"}</td>
                    <td>
                      <AdminStatusBadge tone={item.is_root ? "danger" : "info"}>
                        {item.is_root ? "Root-superadmin" : "Суперадмин"}
                      </AdminStatusBadge>
                    </td>
                    <td>
                      <AdminStatusBadge tone={item.archived_at ? "neutral" : item.is_active ? "success" : "warning"}>
                        {item.archived_at ? "В архиве" : item.is_active ? "Активна" : "Отключена"}
                      </AdminStatusBadge>
                    </td>
                    <td>{formatDateTime(item.created_at)}</td>
                    <td className="text-right">
                      <div className="flex justify-end gap-2">
                        <button type="button" className="admin-button gap-2" onClick={() => setEditingId(item.id)}>
                          <PencilLine className="h-4 w-4" />
                          Редактировать
                        </button>
                        {item.archived_at ? (
                          <button type="button" className="admin-button gap-2" onClick={() => handleRestore(item)} disabled={busyId === item.id}>
                            <RotateCcw className="h-4 w-4" />
                            Восстановить
                          </button>
                        ) : (
                          <button
                            type="button"
                            className="admin-button gap-2 text-rose-300 hover:text-rose-200"
                            onClick={() => handleArchive(item)}
                            disabled={busyId === item.id}
                          >
                            <Trash2 className="h-4 w-4" />
                            Архив
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={8}>Учётки суперадминов пока не созданы.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </AdminCard>

      <AdminModal
        open={editingId !== null}
        onClose={() => {
          if (!isSaving) setEditingId(null);
        }}
        title={draft.id ? "Редактировать superadmin" : "Создать superadmin"}
        description={draft.id ? `ID: #${draft.id}` : "Новая учётка для управления системой."}
        panelClassName="max-w-2xl"
        footer={
          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
            <button type="button" className="admin-button" onClick={() => setEditingId(null)} disabled={isSaving}>
              Отмена
            </button>
            <button type="button" className="admin-primary-button" onClick={handleSave} disabled={isSaving}>
              {isSaving ? "Сохраняем..." : "Сохранить"}
            </button>
          </div>
        }
      >
        <div className="space-y-6">
          <div className="grid gap-4">
            <AdminField label="Логин">
              <input className="admin-input" value={draft.login} onChange={(event) => setDraft((current) => ({ ...current, login: event.target.value }))} />
            </AdminField>
            <AdminField label="Имя суперадмина">
              <input
                className="admin-input"
                value={draft.displayName}
                onChange={(event) => setDraft((current) => ({ ...current, displayName: event.target.value }))}
              />
            </AdminField>
            <AdminField label="Телефон">
              <input className="admin-input" value={draft.phone} onChange={(event) => setDraft((current) => ({ ...current, phone: event.target.value }))} />
            </AdminField>
            <AdminField
              label={draft.id ? "Новый пароль" : "Пароль"}
              hint={draft.id ? "Оставьте пустым, чтобы не менять текущий пароль." : "Пароль нужен для первого входа."}
            >
              <input
                type="password"
                className="admin-input"
                value={draft.password}
                onChange={(event) => setDraft((current) => ({ ...current, password: event.target.value }))}
              />
            </AdminField>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <button
              type="button"
              className="flex items-center gap-3 rounded-2xl border border-border bg-background/70 p-4 text-left"
              onClick={() => setDraft((current) => ({ ...current, isActive: !current.isActive }))}
            >
              <span
                className={`flex h-5 w-5 items-center justify-center rounded-md border transition ${
                  draft.isActive ? "border-blue-500 bg-blue-500 text-white" : "border-border bg-background text-transparent"
                }`}
              >
                <Check className="h-3.5 w-3.5" />
              </span>
              <span className="text-sm font-semibold text-foreground">Учётка активна</span>
            </button>

            <button
              type="button"
              className="flex items-center gap-3 rounded-2xl border border-border bg-background/70 p-4 text-left"
              onClick={() => setDraft((current) => ({ ...current, isRoot: !current.isRoot }))}
            >
              <span
                className={`flex h-5 w-5 items-center justify-center rounded-md border transition ${
                  draft.isRoot ? "border-blue-500 bg-blue-500 text-white" : "border-border bg-background text-transparent"
                }`}
              >
                <Shield className="h-3.5 w-3.5" />
              </span>
              <span className="text-sm font-semibold text-foreground">Root-доступ</span>
            </button>
          </div>
        </div>
      </AdminModal>
    </PageMotion>
  );
}
