const runtime = window.__TOURISTIKA_SUBMISSION__ || {};
let widgetId = null;
let pending = null;
let timeoutId = null;

function settle(kind, value) {
  if (!pending) return;
  const current = pending;
  pending = null;
  if (timeoutId !== null) {
    window.clearTimeout(timeoutId);
    timeoutId = null;
  }
  if (kind === "resolve") current.resolve(value);
  else current.reject(value instanceof Error ? value : new Error(String(value)));
}

function ensureWidget() {
  if (!window.turnstile || typeof window.turnstile.render !== "function") {
    throw new Error("Антиспам-проверка ещё загружается. Повторите отправку.");
  }
  if (widgetId !== null) return widgetId;

  const container = document.createElement("div");
  container.setAttribute("aria-label", "Антиспам-проверка");
  container.style.position = "fixed";
  container.style.right = "max(16px, env(safe-area-inset-right))";
  container.style.bottom = "max(16px, env(safe-area-inset-bottom))";
  container.style.zIndex = "10000";
  document.body.append(container);

  widgetId = window.turnstile.render(container, {
    sitekey: runtime.captchaSiteKey,
    action: runtime.captchaAction,
    execution: "execute",
    appearance: "interaction-only",
    "response-field": false,
    callback: (token) => settle("resolve", token),
    "error-callback": () => settle("reject", new Error("Антиспам-проверка не выполнена. Повторите попытку.")),
    "expired-callback": () => settle("reject", new Error("Проверка устарела. Отправьте заявку ещё раз.")),
    "timeout-callback": () => settle("reject", new Error("Антиспам-проверка заняла слишком много времени.")),
  });
  return widgetId;
}

window.touristikaCaptcha = {
  execute() {
    if (!runtime.captchaSiteKey) {
      return Promise.reject(new Error("Антиспам-проверка не настроена."));
    }
    if (pending) {
      return Promise.reject(new Error("Антиспам-проверка уже выполняется."));
    }
    try {
      const currentWidget = ensureWidget();
      window.turnstile.reset(currentWidget);
      return new Promise((resolve, reject) => {
        pending = { resolve, reject };
        timeoutId = window.setTimeout(
          () => settle("reject", new Error("Антиспам-проверка недоступна. Повторите позднее.")),
          20_000,
        );
        window.turnstile.execute(currentWidget);
      });
    } catch (error) {
      return Promise.reject(error);
    }
  },
  reset() {
    if (widgetId !== null && window.turnstile && typeof window.turnstile.reset === "function") {
      window.turnstile.reset(widgetId);
    }
  },
};
