import type { ChangeDiff } from "./api";
import type { ReactNode } from "react";

const valueLabels: Record<string, string> = {
  contact_type: "Канал",
  label: "Подпись",
  value: "Значение",
  url: "Ссылка",
  is_public: "Показывать публично",
  name: "Название",
  description: "Описание",
  price: "Цена",
  amenity_id: "Удобство",
  accommodation_format: "Формат размещения",
  check_in_time: "Заезд",
  check_out_time: "Выезд",
  duration_minutes: "Продолжительность",
  capacity: "Вместимость",
  meeting_point: "Место встречи",
  pricing_note: "Условия стоимости",
  advance_booking: "Предварительная запись",
  cuisine: "Кухня",
  average_check: "Средний чек",
  reservation_required: "Бронирование",
  delivery: "Доставка",
  experience_years: "Опыт",
  languages: "Языки",
  categories: "Направления",
  license_info: "Квалификация",
  group_size_min: "Минимальная группа",
  group_size_max: "Максимальная группа",
  route_length_km: "Протяжённость маршрута",
};

function humanKey(key: string) {
  return valueLabels[key] || key.replace(/_/g, " ").replace(/^./, (letter) => letter.toUpperCase());
}

function renderValue(value: unknown): ReactNode {
  if (value === null || value === undefined || value === "") return "Не заполнено";
  if (typeof value === "boolean") return value ? "Да" : "Нет";
  if (typeof value === "string" || typeof value === "number") return String(value);
  if (Array.isArray(value)) {
    if (!value.length) return "Не заполнено";
    return (
      <ol className="owner-diff-values">
        {value.map((item, index) => <li key={index}>{renderValue(item)}</li>)}
      </ol>
    );
  }
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>)
      .filter(([, item]) => item !== null && item !== undefined && item !== "");
    if (!entries.length) return "Не заполнено";
    return (
      <dl className="owner-diff-fields">
        {entries.map(([key, item]) => (
          <div key={key}>
            <dt>{humanKey(key)}</dt>
            <dd>{renderValue(item)}</dd>
          </div>
        ))}
      </dl>
    );
  }
  return String(value);
}
export function DiffViewer({ items, title = "Было → Станет" }: { items: ChangeDiff[]; title?: string }) {
  return (
    <section className="owner-card owner-diff" aria-labelledby="owner-diff-title">
      <div className="owner-section-heading">
        <div>
          <p className="owner-eyebrow">Предпросмотр до отправки</p>
          <h2 id="owner-diff-title">{title}</h2>
        </div>
        <span className="owner-count">{items.length}</span>
      </div>
      {items.length ? (
        <div className="owner-diff-list">
          {items.map((item) => (
            <article key={item.field} className="owner-diff-row">
              <h3>{item.label}</h3>
              <div className="owner-diff-columns">
                <div>
                  <span>Было</span>
                  <div className="owner-diff-value">{renderValue(item.before)}</div>
                </div>
                <div aria-hidden="true" className="owner-diff-arrow">→</div>
                <div>
                  <span>Станет</span>
                  <div className="owner-diff-value">{renderValue(item.after)}</div>
                </div>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <p className="owner-empty">Измените поля карточки — здесь появится понятное сравнение.</p>
      )}
    </section>
  );
}
