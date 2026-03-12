import { useMemo, useState, type CSSProperties } from "react";
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

const typeLabels: Record<MarkerType, string> = {
  hotel: "Отель",
  cottage: "Коттедж",
  apartment: "Квартира",
  glamping: "Глэмпинг",
  camping: "Кемпинг",
  villa: "Вилла",
  hostel: "Хостел",
  resort: "Курорт",
  guesthouse: "Гостевой дом",
  bungalow: "Бунгало",
};

const markerColors: Record<MarkerType, { normal: string; vip: string }> = {
  hotel: { normal: "#4a4237", vip: "#6b5d47" },
  cottage: { normal: "#3d4f3a", vip: "#5a7052" },
  apartment: { normal: "#3f4a5c", vip: "#5d6b7e" },
  glamping: { normal: "#5a4f35", vip: "#7d6b46" },
  camping: { normal: "#3d5245", vip: "#557361" },
  villa: { normal: "#524540", vip: "#73625a" },
  hostel: { normal: "#3e4a52", vip: "#5b6a74" },
  resort: { normal: "#3a4f5a", vip: "#547080" },
  guesthouse: { normal: "#4a4037", vip: "#6b5d4f" },
  bungalow: { normal: "#3f4738", vip: "#5c6650" },
};

function hexToRgb(hex: string): string {
  const raw = hex.replace("#", "");
  const full = raw.length === 3 ? raw.split("").map((char) => char + char).join("") : raw;
  const parsed = Number.parseInt(full, 16);
  return `${(parsed >> 16) & 255}, ${(parsed >> 8) & 255}, ${parsed & 255}`;
}

export function MapPopup({
  isOpen,
  onClose,
  onDetails,
  onBook,
  markerType,
  isVIP = false,
  data,
  position,
}: MapPopupProps) {
  const [imageBroken, setImageBroken] = useState(false);
  const accentColor = isVIP ? markerColors[markerType].vip : markerColors[markerType].normal;
  const accentRgb = useMemo(() => hexToRgb(accentColor), [accentColor]);

  const isInline = !position;

  const popupStyle = {
    "--popup-accent": accentColor,
    "--popup-accent-rgb": accentRgb,
    ...(position ? {
      "--popup-left": `${position.left}px`,
      "--popup-top": `${position.top}px`,
      "--popup-width": `${position.width}px`,
      "--popup-pointer-left": `${position.pointerLeft}px`,
    } : {}),
  } as CSSProperties;

  return (
    <AnimatePresence>
      {isOpen ? (
        <div className={`map-popup-widget${isInline ? " map-popup-widget--inline" : ""}`} style={popupStyle}>
          <div className="map-popup-widget__anchor">
            <div className="map-popup-widget__lift">
              <motion.div
                className="map-popup-widget__dialog"
                initial={{ opacity: 0, scale: 0.82, y: 28 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.82, y: 18 }}
                transition={{ type: "spring", stiffness: 420, damping: 28 }}
              >
                {isVIP ? (
                  <motion.div
                    className="map-popup-widget__glow"
                    animate={{
                      opacity: [0, 0.4, 0],
                      scale: [1, 1.05, 1],
                    }}
                    transition={{ duration: 3, repeat: Number.POSITIVE_INFINITY }}
                    style={{
                      background: `radial-gradient(circle, ${accentColor}60 0%, transparent 70%)`,
                      filter: "blur(20px)",
                    }}
                  />
                ) : null}

                <div
                  className="map-popup-widget__card"
                  style={{
                    boxShadow: isVIP
                      ? `0 20px 60px ${accentColor}50, 0 8px 20px rgba(0,0,0,0.15)`
                      : "0 20px 50px rgba(0,0,0,0.2)",
                  }}
                >
                  <motion.button
                    type="button"
                    className="map-popup-widget__close"
                    whileHover={{ scale: 1.08, rotate: 90 }}
                    whileTap={{ scale: 0.92 }}
                    onClick={onClose}
                    aria-label="Закрыть"
                  >
                    <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M6 18L18 6M6 6l12 12"
                      />
                    </svg>
                  </motion.button>

                  <div className="map-popup-widget__badges">
                    <motion.div
                      className="map-popup-widget__badge"
                      initial={{ x: -20, opacity: 0 }}
                      animate={{ x: 0, opacity: 1 }}
                      transition={{ delay: 0.1 }}
                    >
                      <span className="map-popup-widget__badge-dot" aria-hidden="true" />
                      <span>{typeLabels[markerType]}</span>
                    </motion.div>

                    {isVIP ? (
                      <motion.div
                        className="map-popup-widget__vip"
                        initial={{ scale: 0, rotate: -180 }}
                        animate={{ scale: 1, rotate: 0 }}
                        transition={{ type: "spring", delay: 0.2 }}
                      >
                        <svg fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
                          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 0 0 .95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 0 0-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 0 0-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 0 0-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 0 0 .951-.69l1.07-3.292z" />
                        </svg>
                        <span>VIP</span>
                      </motion.div>
                    ) : null}
                  </div>

                  <motion.div
                    className="map-popup-widget__media"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.15 }}
                  >
                    {data.image && !imageBroken ? (
                      <img src={data.image} alt={data.name} onError={() => setImageBroken(true)} />
                    ) : null}
                    {!data.image || imageBroken ? (
                      <div className="map-popup-widget__placeholder" aria-hidden="true">
                        🏕️
                      </div>
                    ) : null}
                    <div className="map-popup-widget__image-overlay" />
                    {isVIP ? (
                      <motion.div
                        className="map-popup-widget__image-shine"
                        animate={{ x: ["-200%", "200%"] }}
                        transition={{ duration: 3, repeat: Number.POSITIVE_INFINITY, repeatDelay: 2 }}
                      />
                    ) : null}
                  </motion.div>

                  <div className="map-popup-widget__body">
                    <motion.h2
                      className="map-popup-widget__title"
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.2 }}
                    >
                      {data.name}
                    </motion.h2>

                    <motion.div
                      className="map-popup-widget__actions"
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.3 }}
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

                    <div className="map-popup-widget__pattern" aria-hidden="true">
                      <svg viewBox="0 0 100 100" fill={accentColor}>
                        <circle cx="80" cy="80" r="40" />
                        <circle cx="60" cy="60" r="25" />
                      </svg>
                    </div>
                  </div>
                </div>

                <motion.div
                  className="map-popup-widget__pointer"
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ delay: 0.35 }}
                  style={{
                    borderTop: `16px solid ${isVIP ? accentColor : "#ede3cd"}`,
                  }}
                />
              </motion.div>
            </div>
          </div>
        </div>
      ) : null}
    </AnimatePresence>
  );
}
