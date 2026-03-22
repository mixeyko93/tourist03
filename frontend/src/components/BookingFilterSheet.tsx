import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";

import type { BookingFilter } from "../lib/booking";
import { windowCardMotion, windowOverlayMotion } from "../lib/windowMotion";

type BookingFilterSheetProps = {
  open: boolean;
  value: BookingFilter | null;
  onClose: () => void;
  onApply: (filter: BookingFilter | null) => void;
};

type DraftFilter = {
  from: string;
  to: string;
  adults: number;
  kids: number;
  allowSplitRooms: boolean;
};

const defaultDraft: DraftFilter = {
  from: "",
  to: "",
  adults: 2,
  kids: 0,
  allowSplitRooms: false,
};

export function BookingFilterSheet({ open, value, onClose, onApply }: BookingFilterSheetProps) {
  const [draft, setDraft] = useState<DraftFilter>(value ?? defaultDraft);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setDraft(value ?? defaultDraft);
    setError(null);
  }, [open, value]);

  const totalGuests = draft.adults + draft.kids;

  function applyFilter() {
    if (!draft.from || !draft.to) {
      setError("Укажите даты заезда и выезда.");
      return;
    }
    if (draft.to <= draft.from) {
      setError("Дата выезда должна быть позже даты заезда.");
      return;
    }
    if (totalGuests <= 0) {
      setError("Укажите хотя бы одного гостя.");
      return;
    }
    if (draft.kids > 0 && draft.adults < 1) {
      setError("Дети могут ехать только со взрослым.");
      return;
    }
    onApply({
      from: draft.from,
      to: draft.to,
      adults: draft.adults,
      kids: draft.kids,
      allowSplitRooms: draft.allowSplitRooms,
    });
  }

  return (
    <AnimatePresence>
      {open ? (
        <motion.div className="sheet-backdrop" onClick={onClose} {...windowOverlayMotion}>
          <motion.div className="sheet-card" onClick={(event) => event.stopPropagation()} {...windowCardMotion}>
            <div className="sheet-card__kicker">Фильтр бронирования</div>
            <h2>Выберите даты и гостей</h2>
            <p>
              После применения карта покажет только те базы, где реально можно
              разместить выбранный состав гостей на нужные даты.
            </p>

            <div className="sheet-grid">
              <label className="sheet-field">
                <span>Заезд</span>
                <input
                  type="date"
                  value={draft.from}
                  onChange={(event) => setDraft((current) => ({ ...current, from: event.target.value }))}
                />
              </label>

              <label className="sheet-field">
                <span>Выезд</span>
                <input
                  type="date"
                  value={draft.to}
                  onChange={(event) => setDraft((current) => ({ ...current, to: event.target.value }))}
                />
              </label>

              <label className="sheet-field">
                <span>Взрослые</span>
                <select
                  value={draft.adults}
                  onChange={(event) => setDraft((current) => ({ ...current, adults: Number(event.target.value) || 1 }))}
                >
                  {Array.from({ length: 30 }, (_, index) => index + 1).map((valueOption) => (
                    <option key={valueOption} value={valueOption}>
                      {valueOption}
                    </option>
                  ))}
                </select>
              </label>

              <label className="sheet-field">
                <span>Дети</span>
                <select
                  value={draft.kids}
                  onChange={(event) => setDraft((current) => ({ ...current, kids: Number(event.target.value) || 0 }))}
                >
                  {Array.from({ length: 31 }, (_, index) => index).map((valueOption) => (
                    <option key={valueOption} value={valueOption}>
                      {valueOption}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <label className="sheet-checkbox">
              <input
                type="checkbox"
                checked={draft.allowSplitRooms}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    allowSplitRooms: event.target.checked,
                  }))
                }
              />
              <span>Показывать варианты с размещением в несколько номеров или домов</span>
            </label>

            <div className="sheet-summary">
              <strong>{totalGuests}</strong> гостей
              <span>
                {draft.adults} взрослых{draft.kids ? `, ${draft.kids} детей` : ""}
              </span>
            </div>

            {error ? <div className="sheet-error">{error}</div> : null}

            <div className="sheet-actions">
              <button type="button" className="sheet-button sheet-button--ghost" onClick={onClose}>
                Закрыть
              </button>
              <button type="button" className="sheet-button sheet-button--ghost" onClick={() => onApply(null)}>
                Сбросить
              </button>
              <button type="button" className="sheet-button" onClick={applyFilter}>
                Применить
              </button>
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
