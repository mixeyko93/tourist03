import { RefreshCcw, RotateCcw, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { PageMotion } from "../../components/PageMotion";
import { usePageLoadState } from "../../components/usePageLoadState";
import { AdminCard } from "../components/AdminCard";
import { AdminStatusBadge } from "../components/AdminStatusBadge";
import {
  deleteSuperadminCamp,
  fetchRootSuperadminAccounts,
  fetchSuperadminBases,
  restoreRootSuperadminAccount,
  updateSuperadminCampStatus,
  type SuperadminBaseSummary,
  type SuperadminRootAccount,
} from "../session";

type ArchiveScope = "bases" | "superadmins";

function formatCurrency(value: number | null | undefined) {
  if (!value) return "Не указана";
  return `${new Intl.NumberFormat("ru-RU").format(value)} ₽`;
}

function formatCoordinates(base: SuperadminBaseSummary) {
  if (base.lat == null || base.lng == null) {
    return "Координаты не заданы";
  }
  return `${base.lat}, ${base.lng}`;
}

function formatDateTime(value?: string | null) {
  if (!value) return "—";
  return new Date(value).toLocaleString("ru-RU");
}

export default function AdminArchivePage() {
  const [scope, setScope] = useState<ArchiveScope>("bases");
  const [bases, setBases] = useState<SuperadminBaseSummary[]>([]);
  const [superadmins, setSuperadmins] = useState<SuperadminRootAccount[]>([]);
  const [canViewSuperadminArchive, setCanViewSuperadminArchive] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);
    setErrorMessage("");
    Promise.allSettled([
      fetchSuperadminBases({ archivedOnly: true, signal: controller.signal }),
      fetchRootSuperadminAccounts({ includeArchived: true, signal: controller.signal }),
    ])
      .then(([baseResult, superadminResult]) => {
        if (baseResult.status === "fulfilled") {
          setBases(baseResult.value);
        } else {
          throw baseResult.reason;
        }
        if (superadminResult.status === "fulfilled") {
          setSuperadmins(superadminResult.value.filter((item) => Boolean(item.archived_at)));
          setCanViewSuperadminArchive(true);
        } else {
          setSuperadmins([]);
          setCanViewSuperadminArchive(false);
          setScope("bases");
        }
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setBases([]);
        setSuperadmins([]);
        setErrorMessage(error instanceof Error ? error.message : "Не удалось загрузить архив");
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      });
    return () => controller.abort();
  }, [reloadKey]);

  const summary = useMemo(
    () => ({
      bases: bases.length,
      superadmins: superadmins.length,
    }),
    [bases.length, superadmins.length],
  );

  async function handleRestoreBase(baseId: number) {
    try {
      setBusyKey(`base:${baseId}`);
      setErrorMessage("");
      setSuccessMessage("");
      await updateSuperadminCampStatus(baseId, "disabled");
      setSuccessMessage("База восстановлена в отключённый список.");
      setReloadKey((value) => value + 1);
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : "Не удалось восстановить базу");
    } finally {
      setBusyKey(null);
    }
  }

  async function handleDeleteBase(baseId: number) {
    if (!window.confirm("Удалить архивную базу безвозвратно?")) {
      return;
    }
    try {
      setBusyKey(`base:${baseId}`);
      setErrorMessage("");
      setSuccessMessage("");
      await deleteSuperadminCamp(baseId);
      setSuccessMessage("Архивная база удалена.");
      setReloadKey((value) => value + 1);
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : "Не удалось удалить архивную базу");
    } finally {
      setBusyKey(null);
    }
  }

  async function handleRestoreSuperadmin(accountId: number) {
    try {
      setBusyKey(`superadmin:${accountId}`);
      setErrorMessage("");
      setSuccessMessage("");
      await restoreRootSuperadminAccount(accountId);
      setSuccessMessage("Учётка суперадмина восстановлена.");
      setReloadKey((value) => value + 1);
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : "Не удалось восстановить суперадмина");
    } finally {
      setBusyKey(null);
    }
  }

  const { isPageVisible } = usePageLoadState(isLoading);

  return (
    <PageMotion className="space-y-6" isReady={isPageVisible}>
      <AdminCard className="overflow-hidden">
        <div className="border-b border-border px-5 py-5 sm:px-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Архив</p>
              <h2 className="mt-2 text-2xl font-semibold tracking-[-0.04em] text-foreground">Единый архив системы</h2>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
                Архивные сущности исключены из рабочих интерфейсов. Здесь их можно восстановить или, если это база, удалить окончательно.
              </p>
            </div>

            <button type="button" className="admin-button gap-2" onClick={() => setReloadKey((value) => value + 1)}>
              <RefreshCcw className="h-4 w-4" />
              Обновить
            </button>
          </div>

          <div className="mt-5 flex flex-wrap gap-3">
            {[
              { key: "bases" as const, label: "Базы", count: summary.bases, visible: true },
              { key: "superadmins" as const, label: "Суперадмины", count: summary.superadmins, visible: canViewSuperadminArchive },
            ]
              .filter((item) => item.visible)
              .map((item) => (
              <button
                key={item.key}
                type="button"
                onClick={() => setScope(item.key)}
                className={`rounded-xl border px-4 py-2 text-sm font-semibold transition ${
                  scope === item.key ? "border-blue-500 bg-blue-500 text-white" : "border-border bg-background/70 text-muted-foreground hover:bg-accent"
                }`}
              >
                {item.label} · {item.count}
              </button>
            ))}
          </div>
        </div>

        {errorMessage ? (
          <div className="border-b border-border bg-rose-500/10 px-5 py-4 text-sm text-rose-300 sm:px-6">{errorMessage}</div>
        ) : null}
        {successMessage ? (
          <div className="border-b border-border bg-emerald-500/10 px-5 py-4 text-sm text-emerald-300 sm:px-6">{successMessage}</div>
        ) : null}

        {scope === "bases" ? (
          <div className="admin-table-shell">
            <table className="admin-table min-w-[900px]">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Название</th>
                  <th>Озеро</th>
                  <th>Координаты</th>
                  <th>Мин. цена</th>
                  <th className="text-right">Действия</th>
                </tr>
              </thead>
              <tbody>
                {isLoading ? (
                  <tr>
                    <td colSpan={6}>Загружаем архив…</td>
                  </tr>
                ) : bases.length ? (
                  bases.map((base) => (
                    <tr key={base.id}>
                      <td>#{base.id}</td>
                      <td className="font-medium text-foreground">
                        <div className="flex items-center gap-3">
                          {base.name || `База #${base.id}`}
                          <AdminStatusBadge tone="neutral">В архиве</AdminStatusBadge>
                        </div>
                      </td>
                      <td>{base.lake_name || "—"}</td>
                      <td>{formatCoordinates(base)}</td>
                      <td>{formatCurrency(base.min_price)}</td>
                      <td className="text-right">
                        <div className="flex justify-end gap-2">
                          <button
                            type="button"
                            className="admin-button gap-2"
                            onClick={() => handleRestoreBase(base.id)}
                            disabled={busyKey === `base:${base.id}`}
                          >
                            <RotateCcw className="h-4 w-4" />
                            {busyKey === `base:${base.id}` ? "Восстанавливаем..." : "Восстановить"}
                          </button>
                          <button
                            type="button"
                            className="admin-button gap-2 text-rose-300 hover:text-rose-200"
                            onClick={() => handleDeleteBase(base.id)}
                            disabled={busyKey === `base:${base.id}`}
                          >
                            <Trash2 className="h-4 w-4" />
                            Удалить
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={6}>Архивных баз пока нет.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="admin-table-shell">
            <table className="admin-table min-w-[900px]">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Логин</th>
                  <th>Имя</th>
                  <th>Роль</th>
                  <th>Архивирована</th>
                  <th className="text-right">Действия</th>
                </tr>
              </thead>
              <tbody>
                {isLoading ? (
                  <tr>
                    <td colSpan={6}>Загружаем архив…</td>
                  </tr>
                ) : superadmins.length ? (
                  superadmins.map((account) => (
                    <tr key={account.id}>
                      <td>#{account.id}</td>
                      <td className="crm-copy-safe font-medium text-foreground">{account.login}</td>
                      <td>{account.display_name}</td>
                      <td>
                        <AdminStatusBadge tone={account.is_root ? "danger" : "info"}>
                          {account.is_root ? "Root-superadmin" : "Суперадмин"}
                        </AdminStatusBadge>
                      </td>
                      <td>{formatDateTime(account.archived_at)}</td>
                      <td className="text-right">
                        <button
                          type="button"
                          className="admin-button gap-2"
                          onClick={() => handleRestoreSuperadmin(account.id)}
                          disabled={busyKey === `superadmin:${account.id}`}
                        >
                          <RotateCcw className="h-4 w-4" />
                          {busyKey === `superadmin:${account.id}` ? "Восстанавливаем..." : "Восстановить"}
                        </button>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={6}>Архивных суперадминов пока нет.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        <div className="border-t border-border bg-background/60 px-5 py-4 text-xs leading-6 text-muted-foreground sm:px-6">
          Восстановление базы возвращает её в список отключённых объектов. Восстановление суперадмина возвращает доступ в панель без автоматического включения лишних root-прав.
        </div>
      </AdminCard>
    </PageMotion>
  );
}
