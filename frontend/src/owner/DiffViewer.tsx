import type { ChangeDiff } from "./api";

function renderValue(value: unknown) {
  if (value === null || value === undefined || value === "") return "Не заполнено";
  if (typeof value === "string" || typeof value === "number") return String(value);
  return JSON.stringify(value, null, 2);
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
                  <pre>{renderValue(item.before)}</pre>
                </div>
                <div aria-hidden="true" className="owner-diff-arrow">→</div>
                <div>
                  <span>Станет</span>
                  <pre>{renderValue(item.after)}</pre>
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
