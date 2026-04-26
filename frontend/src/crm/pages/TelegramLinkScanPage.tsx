import { useEffect, useState } from "react";

declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        initData: string;
        ready(): void;
        close(): void;
        showScanQrPopup(params: { text?: string }, callback: (data: string) => boolean | void): void;
        closeScanQrPopup(): void;
      };
    };
  }
}

type State = "scanning" | "linking" | "success" | "error" | "no_webapp";

export default function TelegramLinkScanPage() {
  const [state, setState] = useState<State>("scanning");
  const [message, setMessage] = useState("");
  const [name, setName] = useState("");

  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    if (!tg) {
      setState("no_webapp");
      return;
    }
    tg.ready();

    tg.showScanQrPopup({ text: "Отсканируйте QR-код из CRM для привязки аккаунта" }, (scannedData) => {
      // Извлекаем код из deep link вида https://t.me/botname?start=CODE или просто CODE
      let code = scannedData.trim();
      const startMatch = code.match(/[?&]start=([^&]+)/);
      if (startMatch) {
        code = startMatch[1];
      }
      if (!code) {
        setMessage("QR-код не содержит кода привязки. Попробуйте ещё раз.");
        setState("error");
        return true; // закрыть попап
      }

      tg.closeScanQrPopup();
      setState("linking");

      fetch("/api/bot/tg-link", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code, init_data: tg.initData }),
      })
        .then(async (resp) => {
          const data = (await resp.json()) as { ok?: boolean; display_name?: string; detail?: string };
          if (!resp.ok) {
            throw new Error(data.detail || "Ошибка привязки");
          }
          setName(data.display_name || "Сотрудник");
          setState("success");
        })
        .catch((err: unknown) => {
          setMessage(err instanceof Error ? err.message : "Не удалось привязать аккаунт");
          setState("error");
        });

      return true;
    });
  }, []);

  const tg = window.Telegram?.WebApp;

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[#18181b] px-6 text-white">
      <div className="w-full max-w-sm text-center">
        {state === "scanning" && (
          <>
            <div className="mb-6 text-5xl">📷</div>
            <h1 className="text-2xl font-semibold">Сканирование QR</h1>
            <p className="mt-3 text-sm leading-6 text-white/60">
              Откроется камера. Наведите на QR-код из CRM (настройки сотрудника → Привязать Telegram).
            </p>
          </>
        )}

        {state === "linking" && (
          <>
            <div className="mb-6 animate-spin text-5xl">⏳</div>
            <h1 className="text-2xl font-semibold">Привязываем...</h1>
            <p className="mt-3 text-sm text-white/60">Подождите несколько секунд.</p>
          </>
        )}

        {state === "success" && (
          <>
            <div className="mb-6 text-5xl">✅</div>
            <h1 className="text-2xl font-semibold">Готово!</h1>
            <p className="mt-3 text-sm leading-6 text-white/70">
              {name}, Telegram успешно привязан к вашей учётке CRM. Теперь вы будете получать уведомления.
            </p>
            <button
              type="button"
              className="mt-6 w-full rounded-2xl bg-white/10 px-4 py-3 text-sm font-semibold transition hover:bg-white/20"
              onClick={() => tg?.close()}
            >
              Закрыть
            </button>
          </>
        )}

        {state === "error" && (
          <>
            <div className="mb-6 text-5xl">❌</div>
            <h1 className="text-2xl font-semibold">Ошибка</h1>
            <p className="mt-3 text-sm leading-6 text-white/70">{message}</p>
            <button
              type="button"
              className="mt-6 w-full rounded-2xl bg-white/10 px-4 py-3 text-sm font-semibold transition hover:bg-white/20"
              onClick={() => window.location.reload()}
            >
              Попробовать ещё раз
            </button>
          </>
        )}

        {state === "no_webapp" && (
          <>
            <div className="mb-6 text-5xl">⚠️</div>
            <h1 className="text-2xl font-semibold">Только в Telegram</h1>
            <p className="mt-3 text-sm leading-6 text-white/70">
              Эта страница предназначена для открытия через бот Telegram. Нажмите кнопку «📷 Сканировать QR» в боте.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
