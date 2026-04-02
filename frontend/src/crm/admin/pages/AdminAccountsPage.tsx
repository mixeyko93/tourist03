import { Check, PencilLine, Plus, RefreshCcw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { PageMotion } from "../../components/PageMotion";
import { AdminCard } from "../components/AdminCard";
import { AdminField } from "../components/AdminField";
import { AdminModal } from "../components/AdminModal";
import { AdminStatusBadge } from "../components/AdminStatusBadge";
import {
  createSuperadminAccount,
  fetchSuperadminAccounts,
  fetchSuperadminBases,
  updateSuperadminAccount,
  type SuperadminAccount,
  type SuperadminBaseSummary,
} from "../session";

type AccountDraft = {
  id: number | null;
  login: string;
  name: string;
  password: string;
  active: boolean;
  baseIds: number[];
};

function createAccountDraft(account: SuperadminAccount | null): AccountDraft {
  if (!account) {
    return {
      id: null,
      login: "",
      name: "",
      password: "",
      active: true,
      baseIds: [],
    };
  }
  return {
    id: account.id,
    login: account.email,
    name: account.display_name,
    password: "",
    active: account.is_active,
    baseIds: account.camps.map((camp) => camp.camp_id),
  };
}

function formatDateTime(value?: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleString("ru-RU");
}

export default function AdminAccountsPage() {
  const [accounts, setAccounts] = useState<SuperadminAccount[]>([]);
  const [bases, setBases] = useState<SuperadminBaseSummary[]>([]);
  const [editingAccountId, setEditingAccountId] = useState<number | "new" | null>(null);
  const [draft, setDraft] = useState<AccountDraft>(() => createAccountDraft(null));
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const currentAccount = typeof editingAccountId === "number" ? accounts.find((item) => item.id === editingAccountId) ?? null : null;
    setDraft(createAccountDraft(currentAccount));
  }, [editingAccountId, accounts]);

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);
    setErrorMessage("");

    Promise.all([
      fetchSuperadminAccounts(controller.signal),
      fetchSuperadminBases({ signal: controller.signal }),
    ])
      .then(([accountItems, baseItems]) => {
        setAccounts(accountItems);
        setBases(baseItems);
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setAccounts([]);
        setBases([]);
        setErrorMessage(error instanceof Error ? error.message : "Не удалось загрузить учётные записи");
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      });

    return () => controller.abort();
  }, [reloadKey]);

  const baseNamesById = useMemo(() => new Map(bases.map((base) => [base.id, base.name || `База #${base.id}`])), [bases]);

  const toggleBase = (baseId: number) => {
    setDraft((current) => ({
      ...current,
      baseIds: current.baseIds.includes(baseId) ? current.baseIds.filter((id) => id !== baseId) : [...current.baseIds, baseId],
    }));
  };

  async function handleSave() {
    try {
      setIsSaving(true);
      setErrorMessage("");
      setSuccessMessage("");
      if (!draft.login.trim()) {
        throw new Error("Укажите email для входа");
      }
      if (!draft.name.trim()) {
        throw new Error("Укажите имя управляющего");
      }
      if (!draft.baseIds.length) {
        throw new Error("Назначьте хотя бы одну базу");
      }
      if (!draft.id && !draft.password.trim()) {
        throw new Error("Для новой учётной записи требуется пароль");
      }

      const payload = {
        email: draft.login.trim(),
        display_name: draft.name.trim(),
        password: draft.password.trim() || undefined,
        is_active: draft.active,
        camp_ids: draft.baseIds,
      };

      if (draft.id) {
        await updateSuperadminAccount(draft.id, payload);
        setSuccessMessage("Учётная запись обновлена.");
      } else {
        await createSuperadminAccount(payload);
        setSuccessMessage("Учётная запись создана.");
      }

      setEditingAccountId(null);
      setReloadKey((value) => value + 1);
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : "Не удалось сохранить учётную запись");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <PageMotion className="space-y-6">
      <AdminCard className="overflow-hidden">
        <div className="flex flex-col gap-4 border-b border-border px-5 py-5 sm:px-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Доступы в CRM</p>
            <h2 className="text-2xl font-semibold tracking-[-0.04em] text-foreground">Учётные записи управляющих</h2>
            <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
              Реальные учётки управляющих и администраторов баз с привязкой к объектам, статусами и быстрым редактированием доступа.
            </p>
          </div>

          <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
            <button type="button" className="admin-button gap-2" onClick={() => setReloadKey((value) => value + 1)}>
              <RefreshCcw className="h-4 w-4" />
              Обновить
            </button>
            <button type="button" className="admin-primary-button w-full gap-2 sm:w-auto" onClick={() => setEditingAccountId("new")}>
              <Plus className="h-4 w-4" />
              Создать учётную запись
            </button>
          </div>
        </div>

        {errorMessage ? (
          <div className="border-b border-border bg-rose-500/10 px-5 py-4 text-sm text-rose-300 sm:px-6">{errorMessage}</div>
        ) : null}
        {successMessage ? (
          <div className="border-b border-border bg-emerald-500/10 px-5 py-4 text-sm text-emerald-300 sm:px-6">{successMessage}</div>
        ) : null}

        <div className="admin-table-shell">
          <table className="admin-table min-w-[1040px]">
            <thead>
              <tr>
                <th>ID</th>
                <th>Логин</th>
                <th>Имя</th>
                <th>Базы отдыха</th>
                <th>Статус</th>
                <th>Создана</th>
                <th className="text-right">Действия</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={7}>Загружаем учётные записи…</td>
                </tr>
              ) : accounts.length ? (
                accounts.map((account) => (
                  <tr key={account.id}>
                    <td>#{account.id}</td>
                    <td className="font-medium text-foreground">{account.email}</td>
                    <td>{account.display_name}</td>
                    <td>
                      <div className="flex flex-wrap gap-2">
                        {account.camps.length ? (
                          account.camps.map((camp) => (
                            <span key={`${account.id}-${camp.camp_id}`} className="rounded-full border border-border bg-background/75 px-3 py-1 text-xs text-foreground">
                              {camp.camp_name || baseNamesById.get(camp.camp_id) || `База #${camp.camp_id}`}
                            </span>
                          ))
                        ) : (
                          <span className="text-muted-foreground">Базы не назначены</span>
                        )}
                      </div>
                    </td>
                    <td>
                      <AdminStatusBadge tone={account.is_active ? "success" : "neutral"}>{account.is_active ? "Активна" : "Отключена"}</AdminStatusBadge>
                    </td>
                    <td>{formatDateTime(account.created_at)}</td>
                    <td className="text-right">
                      <button type="button" className="admin-button gap-2" onClick={() => setEditingAccountId(account.id)}>
                        <PencilLine className="h-4 w-4" />
                        Редактировать
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7}>Учётные записи пока не созданы.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </AdminCard>

      <AdminModal
        open={editingAccountId !== null}
        onClose={() => {
          if (!isSaving) {
            setEditingAccountId(null);
          }
        }}
        title={draft.id ? "Редактировать учётную запись" : "Создать учётную запись"}
        description={draft.id ? `ID: #${draft.id}` : "Новый доступ для управляющего или администратора базы."}
        panelClassName="max-w-2xl"
        footer={
          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
            <button type="button" className="admin-button" onClick={() => setEditingAccountId(null)} disabled={isSaving}>
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
            <AdminField label="Логин (email)">
              <input className="admin-input" value={draft.login} onChange={(event) => setDraft((current) => ({ ...current, login: event.target.value }))} />
            </AdminField>
            <AdminField label={draft.id ? "Новый пароль" : "Пароль"} hint={draft.id ? "Оставьте пустым, чтобы не менять текущий пароль." : "Пароль нужен для первого входа."}>
              <input
                type="password"
                className="admin-input"
                value={draft.password}
                onChange={(event) => setDraft((current) => ({ ...current, password: event.target.value }))}
              />
            </AdminField>
            <AdminField label="Имя управляющего">
              <input className="admin-input" value={draft.name} onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))} />
            </AdminField>
          </div>

          <div className="rounded-2xl border border-border bg-background/70 p-4">
            <button type="button" className="flex items-center gap-3" onClick={() => setDraft((current) => ({ ...current, active: !current.active }))}>
              <span
                className={`flex h-5 w-5 items-center justify-center rounded-md border transition ${
                  draft.active ? "border-blue-500 bg-blue-500 text-white" : "border-border bg-background text-transparent"
                }`}
              >
                <Check className="h-3.5 w-3.5" />
              </span>
              <span className="text-sm font-semibold text-foreground">Учётная запись активна</span>
            </button>
          </div>

          <div className="space-y-3 border-t border-border pt-6">
            <p className="text-sm font-semibold text-foreground">Базы отдыха, доступные учётной записи</p>
            <div className="space-y-3">
              {bases.map((base) => {
                const checked = draft.baseIds.includes(base.id);
                return (
                  <button
                    key={base.id}
                    type="button"
                    className={`flex w-full items-start gap-4 rounded-2xl border p-4 text-left transition ${
                      checked ? "border-blue-500 bg-blue-500/10" : "border-border bg-background/70 hover:bg-accent"
                    }`}
                    onClick={() => toggleBase(base.id)}
                  >
                    <span
                      className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border transition ${
                        checked ? "border-blue-500 bg-blue-500 text-white" : "border-border bg-background text-transparent"
                      }`}
                    >
                      <Check className="h-3.5 w-3.5" />
                    </span>
                    <span>
                      <span className="block text-sm font-semibold text-foreground">{base.name || `База #${base.id}`}</span>
                      <span className="mt-1 block text-xs leading-5 text-muted-foreground">
                        {base.lake_name || "Озеро не указано"}. {base.address || "Адрес не указан"}.
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </AdminModal>
    </PageMotion>
  );
}
