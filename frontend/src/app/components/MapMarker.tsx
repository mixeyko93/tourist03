import { useState, type CSSProperties, type ReactNode } from "react";
import { motion } from "motion/react";

import "./MapMarker.css";

export type MarkerType =
  | "hotel"
  | "cottage"
  | "apartment"
  | "glamping"
  | "camping"
  | "villa"
  | "hostel"
  | "resort"
  | "guesthouse"
  | "bungalow";

export interface MapMarkerProps {
  type: MarkerType;
  price: string;
  isVIP?: boolean;
  onClick?: () => void;
}

type MarkerConfig = {
  label: string;
  color: string;
  vipColor: string;
  icon: ReactNode;
};

const markerConfig: Record<MarkerType, MarkerConfig> = {
  hotel: {
    label: "Отель",
    color: "#4a4237",
    vipColor: "#6b5d47",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <rect x="5" y="8" width="14" height="11" />
        <path d="M7 11h2M11 11h2M15 11h2M7 14h2M11 14h2M15 14h2" />
        <path d="M4 19h16" />
      </svg>
    ),
  },
  cottage: {
    label: "Коттедж",
    color: "#3d4f3a",
    vipColor: "#5a7052",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M3 19h18M5 19v-7l7-5 7 5v7" />
        <rect x="10" y="14" width="4" height="5" />
        <path d="M8 11h2M14 11h2" />
      </svg>
    ),
  },
  apartment: {
    label: "Квартира",
    color: "#3f4a5c",
    vipColor: "#5d6b7e",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <rect x="6" y="5" width="12" height="14" />
        <path d="M9 8h2M13 8h2M9 11h2M13 11h2M9 14h2M13 14h2" />
        <rect x="10" y="16" width="4" height="3" />
      </svg>
    ),
  },
  glamping: {
    label: "Глэмпинг",
    color: "#5a4f35",
    vipColor: "#7d6b46",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 6l6 12H6l6-12z" />
        <path d="M9 13h6M12 13v5" />
      </svg>
    ),
  },
  camping: {
    label: "Кемпинг",
    color: "#3d5245",
    vipColor: "#557361",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 5L4 19h16L12 5z" />
        <path d="M12 5v5" />
      </svg>
    ),
  },
  villa: {
    label: "Вилла",
    color: "#524540",
    vipColor: "#73625a",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M3 19h18M5 19v-8l7-4 7 4v8" />
        <rect x="9" y="13" width="6" height="6" />
        <path d="M11 16h2" />
      </svg>
    ),
  },
  hostel: {
    label: "Хостел",
    color: "#3e4a52",
    vipColor: "#5b6a74",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <rect x="5" y="7" width="14" height="12" />
        <path d="M8 10h3M13 10h3M8 13h3M13 13h3M8 16h8" />
      </svg>
    ),
  },
  resort: {
    label: "Курорт",
    color: "#3a4f5a",
    vipColor: "#547080",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="8" r="2" />
        <path d="M7 19c0-2.76 2.24-5 5-5s5 2.24 5 5" />
        <path d="M4 12h16" />
      </svg>
    ),
  },
  guesthouse: {
    label: "Гостевой дом",
    color: "#4a4037",
    vipColor: "#6b5d4f",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M4 19h16M6 19v-6l6-4 6 4v6" />
        <rect x="10" y="13" width="4" height="6" />
        <circle cx="12" cy="10" r="1" fill="currentColor" stroke="none" />
      </svg>
    ),
  },
  bungalow: {
    label: "Бунгало",
    color: "#3f4738",
    vipColor: "#5c6650",
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M3 18h18M5 18v-6h14v6" />
        <path d="M5 12l7-5 7 5" />
        <rect x="10" y="14" width="4" height="4" />
      </svg>
    ),
  },
};

function hexToRgb(hex: string): string {
  const normalized = hex.replace("#", "");
  const full = normalized.length === 3 ? normalized.split("").map((char) => char + char).join("") : normalized;
  const value = Number.parseInt(full, 16);
  const red = (value >> 16) & 255;
  const green = (value >> 8) & 255;
  const blue = value & 255;
  return `${red}, ${green}, ${blue}`;
}

function buildShadow(color: string, isVIP: boolean, isHovered: boolean): string {
  if (isHovered) {
    if (isVIP) return `0 12px 32px ${color}70, 0 0 50px ${color}40`;
    return `0 10px 28px ${color}60`;
  }
  if (isVIP) return `0 8px 24px ${color}60, 0 0 40px ${color}30`;
  return `0 8px 20px ${color}50`;
}

function VipStar() {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true">
      <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 0 0 .95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 0 0-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 0 0-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 0 0-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 0 0 .951-.69z" />
    </svg>
  );
}

export function MapMarker({ type, price, isVIP = false, onClick }: MapMarkerProps) {
  const [isHovered, setIsHovered] = useState(false);
  const [appearanceDelay] = useState(() => Math.random() * 0.2);

  const config = markerConfig[type];
  const markerColor = isVIP ? config.vipColor : config.color;
  const markerStyle = {
    "--marker-color": markerColor,
    "--marker-rgb": hexToRgb(markerColor),
  } as CSSProperties;

  return (
    <motion.button
      type="button"
      className="map-marker"
      style={markerStyle}
      onHoverStart={() => setIsHovered(true)}
      onHoverEnd={() => setIsHovered(false)}
      onClick={onClick}
      initial={{ opacity: 0, scale: 0.8, y: -20 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{
        type: "spring",
        stiffness: 400,
        damping: 20,
        delay: appearanceDelay,
      }}
      whileHover={{ y: -4 }}
      whileTap={{ scale: 0.95 }}
      aria-label={`${config.label}, ${price}${isVIP ? ", VIP" : ""}`}
    >
      {isVIP ? (
        <motion.div
          className="map-marker__glow"
          animate={{ opacity: [0, 0.3, 0], scale: [1, 1.2, 1] }}
          transition={{ duration: 2, repeat: Number.POSITIVE_INFINITY, ease: "easeInOut" }}
        />
      ) : null}

      <motion.div
        className="map-marker__tooltip"
        initial={false}
        animate={{ opacity: isHovered ? 1 : 0, y: isHovered ? 0 : 10 }}
        transition={{ duration: 0.2 }}
      >
        <span className="map-marker__tooltip-icon">{config.icon}</span>
        <span className="map-marker__tooltip-label">{config.label}</span>
        {isVIP ? <span className="map-marker__tooltip-vip">★</span> : null}
      </motion.div>

      <motion.div
        className="map-marker__badge"
        animate={{ boxShadow: buildShadow(markerColor, isVIP, isHovered) }}
        transition={{ duration: 0.3 }}
      >
        {isVIP ? (
          <>
            <motion.div
              className="map-marker__vip-badge"
              initial={{ scale: 0, rotate: -180 }}
              animate={{ scale: 1, rotate: 0 }}
              transition={{ type: "spring", delay: 0.2 }}
            >
              <VipStar />
            </motion.div>
            <div className="map-marker__shine-wrap" aria-hidden="true">
              <motion.div
                className="map-marker__shine"
                animate={{ x: ["-200%", "200%"] }}
                transition={{
                  duration: 3,
                  repeat: Number.POSITIVE_INFINITY,
                  repeatDelay: 2,
                  ease: "easeInOut",
                }}
              />
            </div>
          </>
        ) : null}

        <div className="map-marker__price">{price}</div>
      </motion.div>

      <motion.div
        className="map-marker__pointer-row"
        animate={{ y: isHovered ? [0, 2, 0] : 0 }}
        transition={{
          duration: 1,
          repeat: isHovered ? Number.POSITIVE_INFINITY : 0,
          ease: "easeInOut",
        }}
      >
        <div className="map-marker__pointer" />
      </motion.div>

      <motion.div
        className="map-marker__shadow"
        animate={{ width: isHovered ? 55 : 50, opacity: isHovered ? 0.3 : 0.2 }}
        transition={{ duration: 0.3 }}
      />
    </motion.button>
  );
}
