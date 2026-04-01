import { RotateCcw, Trash2 } from "lucide-react";
import { PageMotion } from "../../components/PageMotion";
import { AdminCard } from "../components/AdminCard";
import { AdminStatusBadge } from "../components/AdminStatusBadge";
import { archivedBaseRows } from "../mockData";

export default function AdminArchivePage() {
  return (
    <PageMotion className="space-y-6">
      <AdminCard className="overflow-hidden">
        <div className="border-b border-border px-5 py-5 sm:px-6">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Архив</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-[-0.04em] text-foreground">Архив баз отдыха</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
            Список объектов, выведенных из активной витрины. Отсюда базу можно восстановить или удалить окончательно.
          </p>
        </div>

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
              {archivedBaseRows.map((base) => (
                <tr key={base.id}>
                  <td>#{base.id}</td>
                  <td className="font-medium text-foreground">
                    <div className="flex items-center gap-3">
                      {base.name}
                      <AdminStatusBadge tone="neutral">{base.status}</AdminStatusBadge>
                    </div>
                  </td>
                  <td>{base.lake}</td>
                  <td>{base.coordinates}</td>
                  <td>{base.minPrice}</td>
                  <td className="text-right">
                    <div className="flex justify-end gap-2">
                      <button type="button" className="admin-button gap-2">
                        <RotateCcw className="h-4 w-4" />
                        Восстановить
                      </button>
                      <button type="button" className="admin-button gap-2 text-rose-300 hover:text-rose-200">
                        <Trash2 className="h-4 w-4" />
                        Удалить
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="border-t border-border bg-background/60 px-5 py-4 text-xs leading-6 text-muted-foreground sm:px-6">
          Архивные записи исключены из каталога и из доступа управляющих. Возврат в активный список восстанавливает карточку без повторного ввода данных.
        </div>
      </AdminCard>
    </PageMotion>
  );
}
