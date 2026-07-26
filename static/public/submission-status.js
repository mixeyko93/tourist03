const form = document.querySelector("[data-status-form]");
const errorBox = document.querySelector("[data-status-error]");
const result = document.querySelector("[data-status-result]");
const clarificationForm = document.querySelector("[data-clarification-form]");
let activeNumber = "";
let activeToken = "";

function parseFragment() {
  const params = new URLSearchParams(window.location.hash.replace(/^#/, ""));
  const number = params.get("number") || "";
  const token = params.get("token") || "";
  if (number) form.elements.public_number.value = number;
  if (token) form.elements.tracking_token.value = token;
  if (number && token) form.requestSubmit();
}

form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorBox.hidden = true;
  result.hidden = true;
    const number = String(form.elements.public_number.value || "").trim();
    const token = String(form.elements.tracking_token.value || "").trim();
    activeNumber = number;
    activeToken = token;
  try {
    const response = await fetch(`/api/public/submissions/${encodeURIComponent(number)}/status`, {
      headers: { "X-Submission-Tracking-Token": token, Accept: "application/json" },
      credentials: "same-origin",
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || "Заявка не найдена");
    result.querySelector("[data-status-label]").textContent = payload.status_label;
    result.querySelector("[data-status-number]").textContent = payload.public_number;
    result.querySelector("[data-status-comment]").textContent = payload.public_comment || "Комментариев от модератора пока нет.";
    const time = result.querySelector("[data-status-time]");
    const updated = new Date(payload.updated_at);
    time.textContent = Number.isNaN(updated.getTime()) ? "" : `Обновлено ${updated.toLocaleString("ru-RU")}`;
    time.dateTime = payload.updated_at || "";
    const placeLink = result.querySelector("[data-place-link]");
    placeLink.hidden = !payload.place_url;
    if (payload.place_url) placeLink.href = payload.place_url;
    clarificationForm.hidden = !payload.can_respond;
    result.hidden = false;
    result.focus();
  } catch (error) {
    errorBox.textContent = error instanceof Error ? error.message : "Не удалось проверить статус";
    errorBox.hidden = false;
  }
});

clarificationForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorBox.hidden = true;
  const message = String(clarificationForm.elements.message.value || "").trim();
  try {
    const response = await fetch(`/api/public/submissions/${encodeURIComponent(activeNumber)}/clarification`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Submission-Tracking-Token": activeToken,
        Accept: "application/json",
      },
      credentials: "same-origin",
      body: JSON.stringify({ message }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || "Не удалось отправить ответ");
    clarificationForm.hidden = true;
    result.querySelector("[data-status-label]").textContent = payload.status_label;
    result.querySelector("[data-status-comment]").textContent = "Ответ получен и передан модератору.";
  } catch (error) {
    errorBox.textContent = error instanceof Error ? error.message : "Не удалось отправить ответ";
    errorBox.hidden = false;
  }
});

parseFragment();
