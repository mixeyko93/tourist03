import { RefreshCcw, RotateCcw, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { PageMotion } from "../../components/PageMotion";
import { AdminCard } from "../components/AdminCard";
import { AdminStatusBadge } from "../components/AdminStatusBadge";
import { deleteSuperadminCamp, fetchSuperadminBases, updateSuperadminCampStatus, type SuperadminBaseSummary } from "../session";

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

export default function AdminArchivePage() {
  const [items, setItems] = useState<SuperadminBaseSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);
    setErrorMessage("");
    fetchSuperadminBases({ archivedOnly: true, signal: controller.signal })
      .then((bases) => setItems(bases))
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setItems([]);
        setErrorMessage(error instanceof Error ? error.message : "Не удалось загрузить архив");
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      });
    return () => controller.abort();
  }, [reloadKey]);

  async function handleRestore(baseId: number) {
    try {
      setBusyId(baseId);
      setErrorMessage("");
      setSuccessMessage("");
      await updateSuperadminCampStatus(baseId, "disabled");
      setSuccessMessage("База восстановлена в отключённый список.");
      setReloadKey((value) => value + 1);
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : "Не удалось восстановить базу");
    } finally {
      setBusyId(null);
    }
  }

  async function handleDelete(baseId: number) {
    if (!window.confirm("Удалить архивную базу безвозвратно?")) {
      return;
    }
    try {
      setBusyId(baseId);
      setErrorMessage("");
      setSuccessMessage("");
      await deleteSuperadminCamp(baseId);
      setSuccessMessage("Архивная база удалена.");
      setReloadKey((value) => value + 1);
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : "Не удалось удалить архивную базу");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <PageMotion className="space-y-6">
      <AdminCard className="overflow-hidden">
        <div className="border-b border-border px-5 py-5 sm:px-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Архив</p>
              <h2 className="mt-2 text-2xl font-semibold tracking-[-0.04em] text-foreground">Архив баз отдыха</h2>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
                Архивные базы исключены из витрины и рабочих списков CRM. Здесь их можно восстановить или удалить окончательно.
              </p>
            </div>

            <button type="button" className="admin-button gap-2" onClick={() => setReloadKey((value) => value + 1)}>
              <RefreshCcw className="h-4 w-4" />
              Обновить
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
              ) : items.length ? (
                items.map((base) => (
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
                        <button type="button" className="admin-button gap-2" onClick={() => handleRestore(base.id)} disabled={busyId === base.id}>
                          <RotateCcw className="h-4 w-4" />
                          {busyId === base.id ? "Восстанавливаем..." : "Восстановить"}
                        </button>
                        <button
                          type="button"
                          className="admin-button gap-2 text-rose-300 hover:text-rose-200"
                          onClick={() => handleDelete(base.id)}
                          disabled={busyId === base.id}
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

        <div className="border-t border-border bg-background/60 px-5 py-4 text-xs leading-6 text-muted-foreground sm:px-6">
          Восстановление возвращает базу в список отключённых объектов. После проверки карточки её можно снова активировать вручную.
        </div>
      </AdminCard>
    </PageMotion>
  );
}
