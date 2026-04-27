import { Check, PencilLine, Plus, RefreshCcw, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { PageMotion } from "../../components/PageMotion";
import { usePageLoadState } from "../../components/usePageLoadState";
import { AdminCard } from "../components/AdminCard";
import { AdminField } from "../components/AdminField";
import { AdminModal } from "../components/AdminModal";
import { AdminStatusBadge } from "../components/AdminStatusBadge";
import {
  createSuperadminAccount,
  deleteSuperadminAccount,
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
  phone: string;
  password: string;
  active: boolean;
  baseIds: number[];
  roleKey: string;
};

const ROLE_OPTIONS = [{ value: "chief_manager", label: "Управляющий (полный доступ)" }];

const PASSWORD_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789";

const RU_TRANSLIT: Record<string, string> = {
  а: "a",
  б: "b",
  в: "v",
  г: "g",
  д: "d",
  е: "e",
  ё: "e",
  ж: "zh",
  з: "z",
  и: "i",
  й: "i",
  к: "k",
  л: "l",
  м: "m",
  н: "n",
  о: "o",
  п: "p",
  р: "r",
  с: "s",
  т: "t",
  у: "u",
  ф: "f",
  х: "kh",
  ц: "ts",
  ч: "ch",
  ш: "sh",
  щ: "shch",
  ъ: "",
  ы: "y",
  ь: "",
  э: "e",
  ю: "iu",
  я: "ia",
};

function generatePassword(length = 14) {
  const bytes = new Uint32Array(length);
  if (typeof crypto !== "undefined" && crypto.getRandomValues) {
    crypto.getRandomValues(bytes);
  } else {
    for (let index = 0; index < length; index += 1) {
      bytes[index] = Math.floor(Math.random() * 10_000);
    }
  }
  return Array.from(bytes, (value) => PASSWORD_ALPHABET[value % PASSWORD_ALPHABET.length]).join("");
}

function transliterateNamePart(value: string) {
  return value
    .trim()
    .toLowerCase()
    .split("")
    .map((char) => RU_TRANSLIT[char] ?? char)
    .join("")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "")
    .replace(/_{2,}/g, "_");
}

function buildLoginFromFullName(value: string) {
  const [surname = "", name = ""] = value.trim().split(/\s+/).filter(Boolean);
  const loginSurname = transliterateNamePart(surname);
  const loginName = transliterateNamePart(name);
  if (loginSurname && loginName) {
    return `${loginSurname}.${loginName}`;
  }
  return transliterateNamePart(value)
    .replace(/[._-]{2,}/g, ".")
    .replace(/^[._-]+|[._-]+$/g, "");
}

function createAccountDraft(account: SuperadminAccount | null): AccountDraft {
  if (!account) {
    return {
      id: null,
      login: "",
      name: "",
      phone: "",
      password: generatePassword(),
      active: true,
      baseIds: [],
      roleKey: "chief_manager",
    };
  }
  return {
    id: account.id,
    login: account.login,
    name: account.display_name,
    phone: account.phone || "",
    password: "",
    active: account.is_active,
    baseIds: account.camps.map((camp) => camp.camp_id),
    roleKey: account.default_role_key || "chief_manager",
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
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [loginWasEdited, setLoginWasEdited] = useState(false);

  useEffect(() => {
    const currentAccount = typeof editingAccountId === "number" ? accounts.find((item) => item.id === editingAccountId) ?? null : null;
    setDraft(createAccountDraft(currentAccount));
    setLoginWasEdited(Boolean(currentAccount));
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
  const activeAccounts = useMemo(() => accounts.filter((account) => account.is_active), [accounts]);
  const disabledAccounts = useMemo(() => accounts.filter((account) => !account.is_active), [accounts]);

  const toggleBase = (baseId: number) => {
    setDraft((current) => ({
      ...current,
      baseIds: current.baseIds.includes(baseId) ? current.baseIds.filter((id) => id !== baseId) : [...current.baseIds, baseId],
    }));
  };

  const handleDraftNameChange = (value: string) => {
    setDraft((current) => ({
      ...current,
      name: value,
      login: current.id || loginWasEdited ? current.login : buildLoginFromFullName(value),
    }));
  };

  const handleDraftLoginChange = (value: string) => {
    setLoginWasEdited(true);
    setDraft((current) => ({ ...current, login: value }));
  };

  async function handleDelete() {
    if (!draft.id) return;
    if (!deleteConfirm) { setDeleteConfirm(true); return; }
    try {
      setIsDeleting(true);
      setErrorMessage("");
      await deleteSuperadminAccount(draft.id);
      setSuccessMessage("Учётная запись удалена.");
      setEditingAccountId(null);
      setDeleteConfirm(false);
      setReloadKey((value) => value + 1);
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : "Не удалось удалить учётную запись");
    } finally {
      setIsDeleting(false);
    }
  }

  async function handleSave() {
    try {
      setIsSaving(true);
      setErrorMessage("");
      setSuccessMessage("");
      if (!draft.login.trim()) {
        throw new Error("Укажите логин для входа");
      }
      if (!draft.name.trim()) {
        throw new Error("Укажите имя управляющего");
      }
      if (!draft.baseIds.length) {
        throw new Error("Назначьте хотя бы одну базу");
      }
      if (!draft.password.trim() && !draft.id) {
        setDraft((current) => ({ ...current, password: generatePassword() }));
        throw new Error("Пароль создаётся автоматически. Проверьте форму и нажмите сохранить ещё раз.");
      }

      const plainPassword = draft.password.trim();
      const payload = {
        login: draft.login.trim(),
        display_name: draft.name.trim(),
        phone: draft.phone.trim() || undefined,
        password: plainPassword || undefined,
        is_active: draft.active,
        camp_ids: draft.baseIds,
        default_role_key: "chief_manager",
      };

      if (draft.id) {
        await updateSuperadminAccount(draft.id, payload);
        setSuccessMessage(plainPassword ? `Учётная запись обновлена. Новый пароль: ${plainPassword}` : "Учётная запись обновлена.");
      } else {
        await createSuperadminAccount(payload);
        setSuccessMessage(`Учётная запись создана. Пароль: ${plainPassword}`);
      }

      setEditingAccountId(null);
      setReloadKey((value) => value + 1);
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : "Не удалось сохранить учётную запись");
    } finally {
      setIsSaving(false);
    }
  }

  const { isPageVisible } = usePageLoadState(isLoading);

  const renderAccountRows = (items: SuperadminAccount[], emptyText: string) => {
    if (isLoading) {
      return (
        <tr>
          <td colSpan={8}>Загружаем учётные записи…</td>
        </tr>
      );
    }
    if (!items.length) {
      return (
        <tr>
          <td colSpan={8}>{emptyText}</td>
        </tr>
      );
    }
    return items.map((account) => (
      <tr key={account.id}>
        <td>#{account.id}</td>
        <td className="crm-copy-safe font-medium text-foreground">{account.login}</td>
        <td>{account.display_name}</td>
        <td>{ROLE_OPTIONS.find((r) => r.value === account.default_role_key)?.label || "Управляющий (полный доступ)"}</td>
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
    ));
  };

  return (
    <PageMotion className="space-y-6" isReady={isPageVisible}>
      <AdminCard className="overflow-hidden">
        <div className="flex flex-col gap-4 border-b border-border px-5 py-5 sm:px-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Доступы в CRM</p>
            <h2 className="text-2xl font-semibold tracking-[-0.04em] text-foreground">Учётные записи управляющих</h2>
            <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
              Реальные учётки управляющих баз с привязкой к объектам, статусами и быстрым редактированием доступа.
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
                <th>Должность</th>
                <th>Базы отдыха</th>
                <th>Статус</th>
                <th>Создана</th>
                <th className="text-right">Действия</th>
              </tr>
            </thead>
            <tbody>
              {renderAccountRows(activeAccounts, "Активные учётные записи пока не созданы.")}
            </tbody>
          </table>
        </div>
      </AdminCard>

      <AdminCard className="overflow-hidden">
        <div className="border-b border-border px-5 py-5 sm:px-6">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Архив доступа</p>
          <h3 className="mt-2 text-xl font-semibold tracking-[-0.03em] text-foreground">Отключённые учётные записи</h3>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
            Эти учётки не могут войти в CRM и не мешают основному списку активных доступов.
          </p>
        </div>
        <div className="admin-table-shell">
          <table className="admin-table min-w-[1040px]">
            <thead>
              <tr>
                <th>ID</th>
                <th>Логин</th>
                <th>Имя</th>
                <th>Должность</th>
                <th>Базы отдыха</th>
                <th>Статус</th>
                <th>Создана</th>
                <th className="text-right">Действия</th>
              </tr>
            </thead>
            <tbody>{renderAccountRows(disabledAccounts, "Отключённых учётных записей нет.")}</tbody>
          </table>
        </div>
      </AdminCard>

      <AdminModal
        open={editingAccountId !== null}
        onClose={() => {
          if (!isSaving && !isDeleting) {
            setEditingAccountId(null);
            setDeleteConfirm(false);
          }
        }}
        title={draft.id ? "Редактировать учётную запись" : "Создать учётную запись"}
        description={draft.id ? `ID: #${draft.id}` : "Новый доступ для управляющего или администратора базы."}
        panelClassName="max-w-2xl"
        footer={
          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              {draft.id ? (
                <button
                  type="button"
                  className={`inline-flex items-center gap-2 rounded-xl border px-4 py-2 text-sm font-medium transition ${deleteConfirm ? "border-rose-500 bg-rose-500 text-white hover:bg-rose-600" : "border-rose-500/30 bg-rose-500/10 text-rose-400 hover:bg-rose-500/20"}`}
                  onClick={handleDelete}
                  disabled={isDeleting}
                >
                  <Trash2 className="h-4 w-4" />
                  {isDeleting ? "Удаляем..." : deleteConfirm ? "Подтвердить удаление" : "Удалить учётную запись"}
                </button>
              ) : null}
            </div>
            <div className="flex flex-col-reverse gap-3 sm:flex-row">
              <button type="button" className="admin-button" onClick={() => { setEditingAccountId(null); setDeleteConfirm(false); }} disabled={isSaving || isDeleting}>
                Отмена
              </button>
              <button type="button" className="admin-primary-button" onClick={handleSave} disabled={isSaving || isDeleting}>
                {isSaving ? "Сохраняем..." : "Сохранить"}
              </button>
            </div>
          </div>
        }
      >
        <div className="space-y-6">
          <div className="grid gap-4">
            <AdminField label="Фамилия Имя Отчество">
              <input className="admin-input" value={draft.name} onChange={(event) => handleDraftNameChange(event.target.value)} placeholder="Иванов Иван Иванович" title="Фамилия Имя Отчество" />
            </AdminField>
            <AdminField label="Должность">
              <input className="admin-input" value="Управляющий (полный доступ)" title="Должность" readOnly />
            </AdminField>
            <AdminField label="Логин">
              <input className="admin-input" value={draft.login} onChange={(event) => handleDraftLoginChange(event.target.value)} placeholder="иванов.иван" title="Логин для входа в CRM" />
            </AdminField>
            <AdminField label="Номер телефона">
              <input className="admin-input" value={draft.phone} onChange={(event) => setDraft((current) => ({ ...current, phone: event.target.value }))} placeholder="+7 999 000 00 00" title="Номер телефона управляющего" />
            </AdminField>
            <AdminField
              label={draft.id ? "Новый пароль" : "Пароль создан автоматически"}
              hint={draft.id ? "Заполните только если нужно сбросить пароль управляющему." : "Передайте пароль управляющему для первого входа."}
            >
              <div className="flex flex-col gap-2 sm:flex-row">
                <input
                  type="text"
                  className="admin-input"
                  value={draft.password}
                  onChange={(event) => setDraft((current) => ({ ...current, password: event.target.value }))}
                  placeholder={draft.id ? "Нажмите «Сгенерировать пароль» или оставьте пустым" : undefined}
                />
                <button type="button" className="admin-button shrink-0 gap-2" onClick={() => setDraft((current) => ({ ...current, password: generatePassword() }))}>
                  <RefreshCcw className="h-4 w-4" />
                  {draft.id ? "Сгенерировать пароль" : "Обновить пароль"}
                </button>
              </div>
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
