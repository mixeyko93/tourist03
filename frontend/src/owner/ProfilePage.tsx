import { useState } from "react";
import type { FormEvent } from "react";

import { ownerApi, type OwnerDashboard, type OwnerProfile } from "./api";
import { formatDate } from "./components";

export default function ProfilePage({
  dashboard,
  onUpdated,
}: {
  dashboard: OwnerDashboard;
  onUpdated: (owner: OwnerProfile) => void;
}) {
  const [profile, setProfile] = useState(dashboard.owner);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");

  async function save(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const result = await ownerApi.updateProfile({
        display_name: profile.display_name,
        company: profile.company,
        phone: profile.phone,
        telegram: profile.telegram,
        whatsapp: profile.whatsapp,
        max: profile.max,
        preferred_contact_type: profile.preferred_contact_type,
      });
      setProfile(result.owner);
      onUpdated(result.owner);
      setMessage("Профиль сохранён");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось сохранить профиль");
    }
  }

  async function savePassword(event: FormEvent) {
    event.preventDefault();
    setError("");
    setMessage("");
    try {
      const result = await ownerApi.changePassword(currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      setMessage(result.message);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось обновить пароль");
    }
  }

  return (
    <section>
      <div className="owner-page-heading"><div><p className="owner-eyebrow">Аккаунт</p><h1>Профиль владельца</h1><p>Контакты и сводка работы с объектами.</p></div></div>
      <div className="owner-profile-grid">
        <div className="owner-profile-stack">
          <form className="owner-card owner-profile-form" onSubmit={save}>
            <h2>Контактные данные</h2>
            <label>Имя<input required value={profile.display_name} onChange={(event) => setProfile({ ...profile, display_name: event.target.value })} /></label>
            <label>Компания<input value={profile.company || ""} onChange={(event) => setProfile({ ...profile, company: event.target.value })} /></label>
            <label>Телефон<input value={profile.phone || ""} onChange={(event) => setProfile({ ...profile, phone: event.target.value })} /></label>
            <label>Telegram<input value={profile.telegram || ""} onChange={(event) => setProfile({ ...profile, telegram: event.target.value })} /></label>
            <label>WhatsApp<input value={profile.whatsapp || ""} onChange={(event) => setProfile({ ...profile, whatsapp: event.target.value })} /></label>
            <label>MAX<input value={profile.max || ""} onChange={(event) => setProfile({ ...profile, max: event.target.value })} /></label>
            <label className="owner-profile-wide">Предпочтительный способ связи
              <select value={profile.preferred_contact_type || "email"} onChange={(event) => setProfile({ ...profile, preferred_contact_type: event.target.value })}>
                <option value="email">Email</option><option value="phone">Телефон</option><option value="telegram">Telegram</option><option value="whatsapp">WhatsApp</option><option value="max">MAX</option>
              </select>
            </label>
            <button className="owner-primary">Сохранить профиль</button>
          </form>
          <form className="owner-card owner-profile-form owner-password-form" onSubmit={savePassword}>
            <h2>Безопасность</h2>
            <label>Текущий пароль<input required type="password" autoComplete="current-password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} /></label>
            <label>Новый пароль<input required type="password" autoComplete="new-password" minLength={12} value={newPassword} onChange={(event) => setNewPassword(event.target.value)} /></label>
            <button className="owner-secondary">Обновить пароль</button>
          </form>
          {error ? <p className="owner-alert danger" role="alert">{error}</p> : null}
          {message ? <p className="owner-alert success" role="status">{message}</p> : null}
        </div>
        <aside className="owner-card owner-profile-summary">
          <h2>Карточка владельца</h2>
          <dl>
            <div><dt>Email</dt><dd>{profile.email}</dd></div>
            <div><dt>Объектов</dt><dd>{dashboard.profile_statistics.objects_count}</dd></div>
            <div><dt>Дата регистрации</dt><dd>{formatDate(profile.created_at, false)}</dd></div>
            <div><dt>Последний вход</dt><dd>{formatDate(profile.last_login)}</dd></div>
            <div><dt>Способ связи</dt><dd>{{ email: "Email", phone: "Телефон", telegram: "Telegram", whatsapp: "WhatsApp", max: "MAX" }[profile.preferred_contact_type || "email"]}</dd></div>
            <div><dt>Статус</dt><dd>{profile.account_status === "active" ? "Активен" : profile.account_status === "suspended" ? "Приостановлен" : "Ожидает активации"}</dd></div>
            <div><dt>Одобрено</dt><dd>{dashboard.profile_statistics.approved_changes}</dd></div>
            <div><dt>Ожидают</dt><dd>{dashboard.profile_statistics.pending_changes}</dd></div>
            <div><dt>Отклонено</dt><dd>{dashboard.profile_statistics.rejected_changes}</dd></div>
          </dl>
        </aside>
      </div>
    </section>
  );
}
