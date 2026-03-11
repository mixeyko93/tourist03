import { motion } from "framer-motion";
import "./CampMarker.css";

export type CampKind = "house" | "hotel" | "glamping" | "family";
export type CampMarkerSize = "compact" | "default" | "large";

type CampMarkerProps = {
  kind: CampKind;
  price: number;
  name: string;
  size?: CampMarkerSize;
  selected?: boolean;
  vip?: boolean;
  disabled?: boolean;
  onClick?: () => void;
};

type CampClusterProps = {
  count: number;
  large?: boolean;
};

const kindNames: Record<CampKind, string> = {
  house: "Домики",
  hotel: "Lodge",
  glamping: "Глэмпинг",
  family: "Семейная",
};

function formatPrice(price: number): string {
  return `${new Intl.NumberFormat("ru-RU").format(price)}₽`;
}

function CampGlyph({ kind }: { kind: CampKind }) {
  switch (kind) {
    case "hotel":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M4 19h16" />
          <path d="M6 19V8h12v11" />
          <path d="M8 11h2" />
          <path d="M14 11h2" />
          <path d="M8 14h2" />
          <path d="M14 14h2" />
        </svg>
      );
    case "glamping":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="m3 19 9-14 9 14" />
          <path d="M8 13h8" />
          <path d="M10.5 19v-3h3v3" />
        </svg>
      );
    case "family":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M4 18h16" />
          <path d="M6 18v-5l4-3 4 3 4-3v8" />
          <path d="M10 18v-3" />
          <path d="M14 18v-3" />
        </svg>
      );
    case "house":
    default:
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M3 11 12 4l9 7" />
          <path d="M5 10v9h14v-9" />
          <path d="M10 19v-5h4v5" />
        </svg>
      );
  }
}

export function CampMarker({
  kind,
  price,
  name,
  size = "default",
  selected = false,
  vip = false,
  disabled = false,
  onClick,
}: CampMarkerProps) {
  const classes = [
    "camp-marker",
    `camp-marker--${kind}`,
    `camp-marker--${size}`,
    selected ? "camp-marker--selected" : "",
    vip ? "camp-marker--vip" : "",
    disabled ? "camp-marker--disabled" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <motion.button
      type="button"
      className={classes}
      onClick={onClick}
      aria-pressed={selected}
      aria-label={`${name}, ${kindNames[kind]}, от ${formatPrice(price)}`}
      whileHover={disabled ? undefined : { y: -4, scale: 1.02 }}
      whileTap={disabled ? undefined : { scale: 0.98 }}
      animate={
        selected
          ? {
              y: [0, -5, 0],
              transition: {
                duration: 2.1,
                ease: "easeInOut",
                repeat: Number.POSITIVE_INFINITY,
              },
            }
          : {
              y: 0,
            }
      }
      transition={{ type: "spring", stiffness: 260, damping: 18 }}
      disabled={disabled}
    >
      <span className="camp-marker__shadow" />
      <span className="camp-marker__pin">
        <span className="camp-marker__head">
          <span className="camp-marker__glyph">
            <CampGlyph kind={kind} />
          </span>
          <span className="camp-marker__kind">{kindNames[kind]}</span>
        </span>
        <span className="camp-marker__price">{formatPrice(price)}</span>
      </span>
    </motion.button>
  );
}

export function CampCluster({ count, large = false }: CampClusterProps) {
  return (
    <motion.div
      className={`camp-cluster ${large ? "camp-cluster--large" : ""}`}
      initial={{ scale: 0.92, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ type: "spring", stiffness: 240, damping: 18 }}
      aria-label={`Кластер из ${count} баз`}
      role="img"
    >
      {count}
    </motion.div>
  );
}
