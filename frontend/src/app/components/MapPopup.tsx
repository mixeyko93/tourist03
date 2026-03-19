import { useState, type CSSProperties } from "react";
import { AnimatePresence, motion } from "motion/react";

import type { MarkerType } from "./MapMarker";

import "./MapPopup.css";

interface MapPopupData {
  name: string;
  image?: string;
  price: string;
  priceDescription?: string;
}

interface MapPopupPosition {
  left: number;
  top: number;
  width: number;
  pointerLeft: number;
}

export interface MapPopupProps {
  isOpen: boolean;
  onClose: () => void;
  onDetails?: () => void;
  onBook?: () => void;
  markerType: MarkerType;
  isVIP?: boolean;
  data: MapPopupData;
  position?: MapPopupPosition;
}

export function MapPopup({
  isOpen,
  onDetails,
  onBook,
  data,
  position,
}: MapPopupProps) {
  const [imageBroken, setImageBroken] = useState(false);
  const isInline = !position;

  const popupStyle = {
    ...(position
      ? {
          "--popup-left": `${position.left}px`,
          "--popup-top": `${position.top}px`,
          "--popup-width": `${position.width}px`,
          "--popup-pointer-left": `${position.pointerLeft}px`,
        }
      : {}),
  } as CSSProperties;

  return (
    <AnimatePresence>
      {isOpen ? (
        <div className={`map-popup-widget${isInline ? " map-popup-widget--inline" : ""}`} style={popupStyle}>
          <div className="map-popup-widget__anchor">
            <div className="map-popup-widget__lift">
              <motion.div
                className="map-popup-widget__dialog"
                initial={{ opacity: 0, scale: 0.88, y: 24 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.88, y: 16 }}
                transition={{ type: "spring", stiffness: 380, damping: 28 }}
              >
                <div className="map-popup-widget__card">
                  <motion.div
                    className="map-popup-widget__media"
                    initial={{ opacity: 0, scale: 1.02 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.24 }}
                  >
                    {data.image && !imageBroken ? (
                      <img src={data.image} alt={data.name} onError={() => setImageBroken(true)} />
                    ) : null}
                    {(!data.image || imageBroken) && (
                      <div className="map-popup-widget__placeholder" aria-hidden="true">
                        🏕️
                      </div>
                    )}
                    <div className="map-popup-widget__image-overlay" />
                  </motion.div>

                  <div className="map-popup-widget__body">
                    <motion.h2
                      className="map-popup-widget__title"
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.1 }}
                    >
                      {data.name}
                    </motion.h2>

                    <motion.div
                      className="map-popup-widget__actions"
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.18 }}
                    >
                      <motion.button
                        type="button"
                        className="map-popup-widget__button map-popup-widget__button--details"
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        onClick={onDetails}
                      >
                        Подробнее
                      </motion.button>

                      <motion.button
                        type="button"
                        className="map-popup-widget__button map-popup-widget__button--book"
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        onClick={onBook}
                      >
                        Забронировать
                      </motion.button>
                    </motion.div>
                  </div>
                </div>

                <motion.div
                  className="map-popup-widget__pointer"
                  initial={{ opacity: 0, y: -8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -6 }}
                  transition={{ delay: 0.24 }}
                />
              </motion.div>
            </div>
          </div>
        </div>
      ) : null}
    </AnimatePresence>
  );
}
