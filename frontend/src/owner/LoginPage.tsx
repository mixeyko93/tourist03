import { FileClock, ShieldCheck, Sparkles } from "lucide-react";
import { useState } from "react";
import type { FormEvent } from "react";

import { ownerApi, type OwnerProfile } from "./api";
import { ownerResetTokenFromLocation } from "./resetToken";

export default function LoginPage({ onLogin }: { onLogin: (owner: OwnerProfile) => void }) {
  const token = ownerResetTokenFromLocation(window.location.search, window.location.hash);
  const [mode, setMode] = useState<"login" | "forgot" | "reset">(token ? "reset" : "login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      if (mode === "login") {
        const result = await ownerApi.login(email, password);
        onLogin(result.owner);
      } else if (mode === "forgot") {
        const result = await ownerApi.forgot(email);
        setMessage(result.message);
      } else {
        const result = await ownerApi.reset(token, password);
        setMessage(result.message);
        window.history.replaceState({}, "", "/owner");
        setMode("login");
        setPassword("");
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось выполнить действие");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="owner-auth">
      <section className="owner-auth-brand">
        <img
          src="/static/brand/turistika-logo-horizontal-dark.svg"
          width="230"
          height="58"
          alt="Туристика"
        />
        <div>
          <p className="owner-eyebrow">Кабинет владельца</p>
          <h1>Ваша карточка работает лучше, когда всё под контролем.</h1>
          <p>Обновляйте информацию, отправляйте изменения на проверку и следите за состоянием объектов в одном месте.</p>
        </div>
        <ul>
          <li><ShieldCheck /> Публикация только после проверки</li>
          <li><Sparkles /> Подсказки по улучшению карточки</li>
          <li><FileClock /> Полная история изменений</li>
        </ul>
      </section>
      <section className="owner-auth-panel">
        <form className="owner-auth-form" onSubmit={submit}>
          <img src="/static/brand/turistika-icon.svg" width="52" height="52" alt="" className="owner-auth-icon" />
          <p className="owner-eyebrow">Owner Portal</p>
          <h2>{mode === "login" ? "С возвращением" : mode === "forgot" ? "Восстановить доступ" : "Новый пароль"}</h2>
          <p className="owner-muted">
            {mode === "login"
              ? "Войдите, чтобы открыть панель объектов."
              : mode === "forgot"
                ? "Отправим безопасную ссылку на email аккаунта."
                : "Придумайте пароль не короче 12 символов с буквами и цифрами."}
          </p>
          {mode !== "reset" ? (
            <label>Email<input required type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} /></label>
          ) : null}
          {mode !== "forgot" ? (
            <label>{mode === "reset" ? "Новый пароль" : "Пароль"}<input required type="password" minLength={mode === "reset" ? 12 : 1} autoComplete={mode === "reset" ? "new-password" : "current-password"} value={password} onChange={(event) => setPassword(event.target.value)} /></label>
          ) : null}
          {error ? <p className="owner-alert danger" role="alert">{error}</p> : null}
          {message ? <p className="owner-alert success" role="status">{message}</p> : null}
          <button className="owner-primary" disabled={busy}>
            {busy ? "Подождите…" : mode === "login" ? "Войти в кабинет" : mode === "forgot" ? "Отправить ссылку" : "Обновить пароль"}
          </button>
          <button type="button" className="owner-link-button" onClick={() => setMode(mode === "login" ? "forgot" : "login")}>
            {mode === "login" ? "Не помню пароль" : "Вернуться ко входу"}
          </button>
        </form>
      </section>
    </main>
  );
}
