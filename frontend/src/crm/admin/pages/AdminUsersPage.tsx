import { ChevronDown, Clock3, Phone, ShieldCheck, UserRound } from "lucide-react";
import { useState } from "react";
import { PageMotion } from "../../components/PageMotion";
import { AdminCard } from "../components/AdminCard";
import { AdminModal } from "../components/AdminModal";
import { AdminStatusBadge } from "../components/AdminStatusBadge";
import { adminUsers } from "../mockData";

export default function AdminUsersPage() {
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
  const selectedUser = adminUsers.find((user) => user.id === selectedUserId) ?? null;

  return (
    <PageMotion className="space-y-6">
      <AdminCard className="overflow-hidden">
        <div className="border-b border-border px-5 py-5 sm:px-6">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Клиентская база</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-[-0.04em] text-foreground">Пользователи</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
            Единый список клиентов с телефонами, email и деталями активности. Клик по строке открывает полную историю бронирований и событий.
          </p>
        </div>

        <div className="admin-table-shell">
          <table className="admin-table min-w-[940px]">
            <thead>
              <tr>
                {["ID", "Имя", "Телефон", "Email", "Создан"].map((label) => (
                  <th key={label}>
                    <span className="inline-flex items-center gap-1">
                      {label}
                      <ChevronDown className="h-3.5 w-3.5" />
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {adminUsers.map((user) => (
                <tr key={user.id} className="cursor-pointer" onClick={() => setSelectedUserId(user.id)}>
                  <td>{user.id}</td>
                  <td className="font-medium text-foreground">{user.name}</td>
                  <td>{user.phone}</td>
                  <td>{user.email || "—"}</td>
                  <td>{user.createdAt}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </AdminCard>

      <AdminModal
        open={Boolean(selectedUser)}
        onClose={() => setSelectedUserId(null)}
        title={selectedUser ? `Пользователь #${selectedUser.id} — ${selectedUser.name}` : ""}
        description="Детали профиля, история бронирований и события по аккаунту."
        panelClassName="max-w-5xl"
      >
        {selectedUser ? (
          <div className="space-y-6">
            <div className="grid gap-4 lg:grid-cols-3">
              <div className="rounded-3xl border border-border bg-background/65 p-5">
                <div className="flex items-center gap-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-500/10 text-blue-500">
                    <UserRound className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-foreground">{selectedUser.name}</p>
                    <p className="text-xs text-muted-foreground">Профиль пользователя</p>
                  </div>
                </div>
                <div className="mt-4 space-y-3 text-sm">
                  <p className="inline-flex items-center gap-2 text-foreground">
                    <Phone className="h-4 w-4 text-blue-500" />
                    {selectedUser.phone}
                  </p>
                  <p className="text-muted-foreground">{selectedUser.email || "Email не указан"}</p>
                  <p className="text-muted-foreground">Создан: {selectedUser.createdAt}</p>
                </div>
              </div>

              <div className="rounded-3xl border border-border bg-background/65 p-5">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">Статус</p>
                <div className="mt-3">
                  <AdminStatusBadge tone={selectedUser.email ? "info" : "neutral"}>{selectedUser.status}</AdminStatusBadge>
                </div>
                <p className="mt-4 text-sm leading-6 text-muted-foreground">
                  Бронирований: {selectedUser.bookings.length}. Событий в журнале: {selectedUser.events.length}.
                </p>
              </div>

              <div className="rounded-3xl border border-border bg-background/65 p-5">
                <div className="flex items-center gap-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-emerald-500/10 text-emerald-300">
                    <ShieldCheck className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-foreground">Проверка профиля</p>
                    <p className="text-xs text-muted-foreground">Состояние контактных данных</p>
                  </div>
                </div>
                <div className="mt-4 space-y-2 text-sm text-muted-foreground">
                  <p>Телефон: {selectedUser.phone ? "указан" : "не указан"}</p>
                  <p>Email: {selectedUser.email ? "указан" : "не указан"}</p>
                  <p>Последняя активность: {selectedUser.events[0]?.at ?? "нет данных"}</p>
                </div>
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Clock3 className="h-4 w-4 text-blue-500" />
                <h3 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">Бронирования</h3>
              </div>
              <div className="admin-table-shell">
                <table className="admin-table min-w-[820px]">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>База</th>
                      <th>Номер</th>
                      <th>Даты</th>
                      <th>Гостей</th>
                      <th>Статус</th>
                      <th>Создано</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedUser.bookings.length ? (
                      selectedUser.bookings.map((booking) => (
                        <tr key={booking.id}>
                          <td>{booking.id}</td>
                          <td className="font-medium text-foreground">{booking.base}</td>
                          <td>{booking.room}</td>
                          <td>{booking.dates}</td>
                          <td>{booking.guests}</td>
                          <td>
                            <AdminStatusBadge
                              tone={
                                booking.status === "Подтверждена" ? "success" : booking.status === "Ожидание" ? "warning" : "info"
                              }
                            >
                              {booking.status}
                            </AdminStatusBadge>
                          </td>
                          <td>{booking.createdAt}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={7}>Нет бронирований.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Clock3 className="h-4 w-4 text-blue-500" />
                <h3 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">События</h3>
              </div>
              <div className="admin-table-shell">
                <table className="admin-table min-w-[760px]">
                  <thead>
                    <tr>
                      <th>Время</th>
                      <th>Событие</th>
                      <th>Данные</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedUser.events.length ? (
                      selectedUser.events.map((event) => (
                        <tr key={`${event.at}-${event.event}`}>
                          <td>{event.at}</td>
                          <td className="font-medium text-foreground">{event.event}</td>
                          <td>{event.data}</td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={3}>Пока нет событий по пользователю.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        ) : null}
      </AdminModal>
    </PageMotion>
  );
}
