import { AnimatePresence, motion } from "motion/react";

import { FacilityIcon } from "./FacilityIcons";
import type { ApartmentFacility } from "./ApartmentDetailModal";
import "./ApartmentModals.css";

export interface ApartmentParamsModalProps {
  isOpen: boolean;
  title?: string;
  subtitle?: string;
  facilities: ApartmentFacility[];
  onBack?: () => void;
}

export function ApartmentParamsModal({
  isOpen,
  title = "Параметры апартамента",
  subtitle,
  facilities,
  onBack,
}: ApartmentParamsModalProps) {
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
                {subtitle ? <p className="apartment-modal-subtitle">{subtitle}</p> : null}
              </header>

              <div className="apartment-facility-grid">
                {facilities.map((facility) => (
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

              <div className="apartment-modal-actions--single">
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

export default ApartmentParamsModal;
