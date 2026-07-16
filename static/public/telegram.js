export function initialiseTelegramWebApp(features) {
  const webApp = window.Telegram?.WebApp;
  if (!features.telegram_webapp || !webApp) return false;

  try {
    webApp.ready?.();
    webApp.expand?.();
    document.documentElement.classList.add("is-telegram-webapp");
    webApp.onEvent?.("viewportChanged", () => webApp.expand?.());
    return true;
  } catch {
    return false;
  }
}
