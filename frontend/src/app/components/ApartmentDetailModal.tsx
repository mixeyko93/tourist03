import { AnimatePresence, motion } from "motion/react";
import { useEffect, useMemo, useState } from "react";

import { FacilityIcon, type FacilityIconName } from "./FacilityIcons";
import "./ApartmentModals.css";

export interface ApartmentFacility {
  id: string;
  label: string;
  value: string;
  icon: FacilityIconName;
}

export interface ApartmentDetailModalProps {
  isOpen: boolean;
  title: string;
  images: string[];
  facilities: ApartmentFacility[];
  adultPrice?: string;
  childPrice?: string;
  onChoose?: () => void;
  onBack?: () => void;
  onOpenAllParams?: () => void;
}

function Chevron({ direction }: { direction: "left" | "right" }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d={direction === "left" ? "M15 5l-7 7 7 7" : "M9 5l7 7-7 7"}
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function sanitizeImages(images: string[]) {
  return images.filter((image) => typeof image === "string" && image.trim().length > 0);
}

export function ApartmentDetailModal({
  isOpen,
  title,
  images,
  facilities,
  adultPrice,
  childPrice,
  onChoose,
  onBack,
  onOpenAllParams,
}: ApartmentDetailModalProps) {
  const gallery = useMemo(() => sanitizeImages(images), [images]);
  const [activeIndex, setActiveIndex] = useState(0);

  useEffect(() => {
    setActiveIndex(0);
  }, [title, gallery.length]);

  useEffect(() => {
    if (!gallery.length) {
      setActiveIndex(0);
      return;
    }
    if (activeIndex > gallery.length - 1) {
      setActiveIndex(gallery.length - 1);
    }
  }, [activeIndex, gallery]);

  function goTo(offset: number) {
    if (!gallery.length) return;
    setActiveIndex((current) => (current + offset + gallery.length) % gallery.length);
  }

  const compactFacilities = facilities.slice(0, 6);

  return (
    <AnimatePresence>
      {isOpen ? (
        <motion.div
          className="apartment-modal-overlay"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <motion.div
            className="apartment-modal-card"
            initial={{ opacity: 0, y: 28, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.96 }}
            transition={{ type: "spring", stiffness: 280, damping: 28 }}
          >
            <div className="apartment-modal-scroller">
              <header className="apartment-modal-header">
                <h2 className="apartment-modal-title">{title}</h2>
              </header>

              <div className="apartment-gallery">
                {gallery[activeIndex] ? <img src={gallery[activeIndex]} alt={title} /> : null}
                {gallery.length > 1 ? (
                  <>
                    <button
                      type="button"
                      className="apartment-gallery__nav apartment-gallery__nav--prev"
                      onClick={() => goTo(-1)}
                      aria-label="Предыдущее фото"
                    >
                      <Chevron direction="left" />
                    </button>
                    <button
                      type="button"
                      className="apartment-gallery__nav apartment-gallery__nav--next"
                      onClick={() => goTo(1)}
                      aria-label="Следующее фото"
                    >
                      <Chevron direction="right" />
                    </button>
                    <div className="apartment-gallery__counter">
                      {activeIndex + 1} / {gallery.length}
                    </div>
                  </>
                ) : null}
              </div>

              <div className="apartment-facility-grid">
                {compactFacilities.map((facility) => (
                  <div key={facility.id} className="apartment-facility-card">
                    <div className="apartment-facility-card__icon" aria-hidden="true">
                      <FacilityIcon name={facility.icon} />
                    </div>
                    <div className="apartment-facility-card__meta">
                      <p className="apartment-facility-card__label">{facility.label}</p>
                      <p className="apartment-facility-card__value">{facility.value}</p>
                    </div>
                  </div>
                ))}
              </div>

              <button type="button" className="apartment-modal-toggle" onClick={onOpenAllParams}>
                Открыть все параметры апартамента
              </button>

              {(adultPrice || childPrice) && (
                <div className="apartment-prices">
                  <div className="apartment-prices__item">
                    <span className="apartment-prices__label">Взрослый</span>
                    <span className="apartment-prices__value">{adultPrice || "—"}</span>
                  </div>
                  <div className="apartment-prices__item">
                    <span className="apartment-prices__label">Ребёнок</span>
                    <span className="apartment-prices__value">{childPrice || "—"}</span>
                  </div>
                </div>
              )}

              <div className="apartment-modal-actions">
                <motion.button
                  type="button"
                  className="apartment-modal-button apartment-modal-button--accent"
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={onChoose}
                >
                  Выбрать
                </motion.button>
                <motion.button
                  type="button"
                  className="apartment-modal-button"
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={onBack}
                >
                  Назад
                </motion.button>
              </div>
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

export default ApartmentDetailModal;
