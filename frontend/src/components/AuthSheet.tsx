import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";

import type { StoredAuth } from "../lib/auth";
import { windowCardMotion, windowOverlayMotion } from "../lib/windowMotion";
import type { AuthTokenUserResponse } from "../types/auth";

type AuthSheetProps = {
  open: boolean;
  onClose: () => void;
  onSuccess: (auth: StoredAuth) => void;
};

export function AuthSheet({ open, onClose, onSuccess }: AuthSheetProps) {
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [step, setStep] = useState<"phone" | "code">("phone");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    setStep("phone");
    setError(null);
    setCode("");
  }, [open]);

  async function startLogin() {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/auth/login/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ phone }),
      });
      const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
      if (!response.ok) {
        throw new Error(payload?.detail || `Ошибка (${response.status})`);
      }
      setStep("code");
    } catch (errorValue) {
      setError(errorValue instanceof Error ? errorValue.message : "Не удалось отправить код.");
    } finally {
      setIsLoading(false);
    }
  }

  async function verifyLogin() {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/auth/login/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ phone, code }),
      });
      const payload = (await response.json().catch(() => null)) as AuthTokenUserResponse | { detail?: string } | null;
      if (!response.ok || !payload || !("user" in payload) || !payload.token) {
        throw new Error(
          payload && typeof payload === "object" && "detail" in payload
            ? String(payload.detail || "Не удалось войти.")
            : "Не удалось войти.",
        );
      }
      onSuccess({ token: payload.token, user: payload.user });
      onClose();
    } catch (errorValue) {
      setError(errorValue instanceof Error ? errorValue.message : "Не удалось подтвердить код.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <AnimatePresence>
      {open ? (
        <motion.div className="sheet-backdrop" onClick={onClose} {...windowOverlayMotion}>
          <motion.div
            className="sheet-card sheet-card--narrow"
            onClick={(event) => event.stopPropagation()}
            {...windowCardMotion}
          >
            <div className="sheet-card__kicker">Вход для бронирования</div>
            <h2>Войдите по номеру телефона</h2>
            <p>
              Новый экран уже использует тот же auth API. Для бронирования нужен
              существующий аккаунт пользователя.
            </p>

            <label className="sheet-field">
              <span>Телефон</span>
              <input
                type="tel"
                placeholder="+7 900 000 00 00"
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
              />
            </label>

            {step === "code" ? (
              <label className="sheet-field">
                <span>Код подтверждения</span>
                <input
                  type="text"
                  inputMode="numeric"
                  value={code}
                  onChange={(event) => setCode(event.target.value)}
                />
              </label>
            ) : null}

            {error ? <div className="sheet-error">{error}</div> : null}

            <div className="sheet-actions">
              <button type="button" className="sheet-button sheet-button--ghost" onClick={onClose}>
                Закрыть
              </button>
              {step === "phone" ? (
                <button type="button" className="sheet-button" onClick={() => void startLogin()} disabled={isLoading || !phone.trim()}>
                  {isLoading ? "Отправка..." : "Получить код"}
                </button>
              ) : (
                <button
                  type="button"
                  className="sheet-button"
                  onClick={() => void verifyLogin()}
                  disabled={isLoading || !phone.trim() || !code.trim()}
                >
                  {isLoading ? "Проверка..." : "Войти"}
                </button>
              )}
            </div>

            <div className="sheet-note">
              Если аккаунта ещё нет, регистрацию пока нужно пройти в старом пользовательском экране.
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
