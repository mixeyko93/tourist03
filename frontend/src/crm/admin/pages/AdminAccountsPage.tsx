import { Check, PencilLine, Plus } from "lucide-react";
import { useEffect, useState } from "react";
import { PageMotion } from "../../components/PageMotion";
import { AdminCard } from "../components/AdminCard";
import { AdminField } from "../components/AdminField";
import { AdminModal } from "../components/AdminModal";
import { AdminStatusBadge } from "../components/AdminStatusBadge";
import { adminAccounts, adminBaseRows, getAccountBaseNames } from "../mockData";

type AccountDraft = {
  id: string;
  login: string;
  name: string;
  password: string;
  active: boolean;
  baseIds: string[];
};

function createAccountDraft(accountId: string | null): AccountDraft {
  const source = accountId ? adminAccounts.find((account) => account.id === accountId) : null;
  if (!source) {
    return {
      id: "new",
      login: "",
      name: "",
      password: "",
      active: true,
      baseIds: [],
    };
  }
  return {
    id: source.id,
    login: source.login,
    name: source.name,
    password: "",
    active: source.status === "Активна",
    baseIds: [...source.baseIds],
  };
}

export default function AdminAccountsPage() {
  const [editingAccountId, setEditingAccountId] = useState<string | null>(null);
  const [draft, setDraft] = useState<AccountDraft>(() => createAccountDraft(null));

  useEffect(() => {
    setDraft(createAccountDraft(editingAccountId));
  }, [editingAccountId]);

  const toggleBase = (baseId: string) => {
    setDraft((current) => ({
      ...current,
      baseIds: current.baseIds.includes(baseId)
        ? current.baseIds.filter((id) => id !== baseId)
        : [...current.baseIds, baseId],
    }));
  };

  return (
    <PageMotion className="space-y-6">
      <AdminCard className="overflow-hidden">
        <div className="flex flex-col gap-4 border-b border-border px-5 py-5 sm:px-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Доступы в CRM</p>
            <h2 className="text-2xl font-semibold tracking-[-0.04em] text-foreground">Учётные записи управляющих</h2>
            <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
              Создавайте аккаунты для управляющих, отключайте доступ и назначайте видимость конкретных баз отдыха через кастомные чекбоксы.
            </p>
          </div>

          <button type="button" className="admin-primary-button w-full gap-2 sm:w-auto" onClick={() => setEditingAccountId("new")}>
            <Plus className="h-4 w-4" />
            Создать учётную запись
          </button>
        </div>

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
              {adminAccounts.map((account) => (
                <tr key={account.id}>
                  <td>#{account.id}</td>
                  <td className="font-medium text-foreground">{account.login}</td>
                  <td>{account.name}</td>
                  <td>
                    <div className="flex flex-wrap gap-2">
                      {getAccountBaseNames(account.baseIds).map((baseName) => (
                        <span key={baseName} className="rounded-full border border-border bg-background/75 px-3 py-1 text-xs text-foreground">
                          {baseName}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td>
                    <AdminStatusBadge tone={account.status === "Активна" ? "success" : "neutral"}>{account.status}</AdminStatusBadge>
                  </td>
                  <td>{account.createdAt}</td>
                  <td className="text-right">
                    <button type="button" className="admin-button gap-2" onClick={() => setEditingAccountId(account.id)}>
                      <PencilLine className="h-4 w-4" />
                      Редактировать
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </AdminCard>

      <AdminModal
        open={editingAccountId !== null}
        onClose={() => setEditingAccountId(null)}
        title={draft.id === "new" ? "Создать учётную запись" : "Редактировать учётную запись"}
        description={draft.id === "new" ? "Новый доступ для управляющего." : `ID: #${draft.id}`}
        panelClassName="max-w-2xl"
        footer={
          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
            <button type="button" className="admin-button" onClick={() => setEditingAccountId(null)}>
              Отмена
            </button>
            <button type="button" className="admin-primary-button">
              Сохранить
            </button>
          </div>
        }
      >
        <div className="space-y-6">
          <div className="grid gap-4">
            <AdminField label="Логин (email)">
              <input className="admin-input" value={draft.login} onChange={(event) => setDraft((current) => ({ ...current, login: event.target.value }))} />
            </AdminField>
            <AdminField label="Новый пароль" hint="Оставьте пустым, чтобы не менять текущий пароль.">
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
            <button
              type="button"
              className="flex items-center gap-3"
              onClick={() => setDraft((current) => ({ ...current, active: !current.active }))}
            >
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
              {adminBaseRows.map((base) => {
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
                      <span className="block text-sm font-semibold text-foreground">{base.name}</span>
                      <span className="mt-1 block text-xs leading-5 text-muted-foreground">
                        {base.lake}. {base.coordinates}. Управляющий: {base.manager}
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
