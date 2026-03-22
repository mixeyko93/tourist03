import { AnimatePresence, motion } from "motion/react";

import { windowCardMotion, windowOverlayMotion } from "../../lib/windowMotion";
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
          {...windowOverlayMotion}
        >
          <motion.div
            className="apartment-modal-card"
            {...windowCardMotion}
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
