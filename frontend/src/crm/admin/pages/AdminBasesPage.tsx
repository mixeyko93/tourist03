import { Compass, PencilLine, Plus } from "lucide-react";
import { useNavigate } from "react-router";
import { PageMotion } from "../../components/PageMotion";
import { crmPath } from "../../paths";
import { AdminCard } from "../components/AdminCard";
import { AdminStatusBadge } from "../components/AdminStatusBadge";
import { adminBaseRows } from "../mockData";

export default function AdminBasesPage() {
  const navigate = useNavigate();

  return (
    <PageMotion className="space-y-6">
      <AdminCard className="overflow-hidden">
        <div className="flex flex-col gap-4 border-b border-border px-5 py-5 sm:px-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-2">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Справочник баз</p>
              <h2 className="text-2xl font-semibold tracking-[-0.04em] text-foreground">Базы отдыха и номерной фонд</h2>
              <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
                Управление карточками объектов, контактами владельцев, координатами, минимальными тарифами и доступом управляющих.
              </p>
            </div>
            <button type="button" className="admin-primary-button w-full gap-2 sm:w-auto" onClick={() => navigate(crmPath("/admin/bases/new"))}>
              <Plus className="h-4 w-4" />
              Добавить базу
            </button>
          </div>
        </div>

        <div className="admin-table-shell">
          <table className="admin-table min-w-[1180px]">
            <thead>
              <tr>
                <th>Статус</th>
                <th>ID</th>
                <th>Название</th>
                <th>Озеро</th>
                <th>Координаты</th>
                <th>Владелец</th>
                <th>Управляющий</th>
                <th>Мин. цена</th>
                <th className="text-right">Действия</th>
              </tr>
            </thead>
            <tbody>
              {adminBaseRows.map((base) => (
                <tr key={base.id}>
                  <td>
                    <AdminStatusBadge tone="success">{base.status}</AdminStatusBadge>
                  </td>
                  <td className="text-muted-foreground">#{base.id}</td>
                  <td className="font-medium text-foreground">{base.name}</td>
                  <td>{base.lake}</td>
                  <td>
                    <span className="inline-flex items-center gap-2">
                      <Compass className="h-4 w-4 text-muted-foreground" />
                      {base.coordinates}
                    </span>
                  </td>
                  <td className="max-w-[260px] leading-6">{base.owner}</td>
                  <td className="max-w-[260px] leading-6">{base.manager}</td>
                  <td className="font-medium text-foreground">{base.minPrice}</td>
                  <td className="text-right">
                    <button type="button" className="admin-button gap-2" onClick={() => navigate(crmPath(`/admin/bases/${base.id}`))}>
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
    </PageMotion>
  );
}
