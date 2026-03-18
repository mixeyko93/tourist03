import { motion } from "motion/react";
import { useState, type ReactNode } from "react";
import {
  Bell,
  Calendar,
  HelpCircle,
  Map,
  MapPin,
  RotateCw,
  ShoppingCart,
  User,
} from "lucide-react";

export type MapScreenView = "map" | "profile" | "services" | "help";

export interface MapScreenProps {
  mapContent?: ReactNode;
  cartCount?: number;
  initialView?: MapScreenView;
  onRefreshMap?: () => void;
  onGetLocation?: () => void;
  onOpenFilter?: () => void;
  onOpenCart?: () => void;
  onChangeView?: (view: MapScreenView) => void;
}

type NavItem = {
  key: MapScreenView;
  label: string;
  Icon: typeof Map;
};

const navItems: NavItem[] = [
  { key: "map", label: "Карта", Icon: Map },
  { key: "profile", label: "Личный кабинет", Icon: User },
  { key: "services", label: "Услуги", Icon: Bell },
  { key: "help", label: "Помощь", Icon: HelpCircle },
];

const glassButtonClass =
  "bg-[#1a1a1a]/90 backdrop-blur-xl shadow-2xl border border-white/10 hover:bg-[#2a2a2a]/90 transition-colors";

const iconButtonMotion = {
  whileHover: { scale: 1.1 },
  whileTap: { scale: 0.95 },
  transition: { type: "spring", stiffness: 380, damping: 26 },
} as const;

export function MapScreen({
  mapContent,
  cartCount = 2,
  initialView = "map",
  onRefreshMap,
  onGetLocation,
  onOpenFilter,
  onOpenCart,
  onChangeView,
}: MapScreenProps) {
  const [currentView, setCurrentView] = useState<MapScreenView>(initialView);

  function handleChangeView(view: MapScreenView) {
    setCurrentView(view);
    onChangeView?.(view);
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-black">
      <div className="relative flex-1">
        <div className="absolute inset-0 m-3 overflow-hidden rounded-[28px] shadow-2xl md:m-6 md:rounded-[32px]">
          <div className="absolute inset-0 bg-neutral-200">
            {mapContent ?? <div className="h-full w-full bg-[#d9d9d9]" id="map-container" />}
          </div>

          <motion.button
            type="button"
            aria-label="Обновить карту"
            className="absolute right-4 top-4 z-[500] flex items-center justify-center rounded-full border border-white/10 bg-[#2a2a2a]/90 p-1.5 text-white shadow-2xl backdrop-blur-xl transition-colors hover:bg-[#3a3a3a]/90 md:right-6 md:top-6 md:p-2"
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ type: "spring", stiffness: 320, damping: 28, delay: 0.25 }}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={onRefreshMap}
          >
            <RotateCw className="h-4 w-4 md:h-4 md:w-4" strokeWidth={2.2} />
          </motion.button>

          <div className="pointer-events-none absolute inset-x-0 bottom-4 z-[500] flex items-end justify-between px-4 md:bottom-6 md:px-6">
            <motion.div
              className="pointer-events-auto"
              initial={{ opacity: 0, x: -18, y: 20 }}
              animate={{ opacity: 1, x: 0, y: 0 }}
              transition={{ type: "spring", stiffness: 320, damping: 28, delay: 0.12 }}
            >
              <motion.button
                type="button"
                aria-label="Открыть фильтры"
                className={`${glassButtonClass} rounded-full p-3.5 md:p-5`}
                onClick={onOpenFilter}
                {...iconButtonMotion}
              >
                <Calendar className="h-6 w-6 text-white md:h-7 md:w-7" strokeWidth={2} />
              </motion.button>
            </motion.div>

            <motion.div
              className="pointer-events-auto mb-1"
              initial={{ opacity: 0, scale: 0.82, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              transition={{ type: "spring", stiffness: 340, damping: 28, delay: 0.18 }}
            >
              <motion.button
                type="button"
                aria-label="Открыть корзину"
                className="relative rounded-full border-2 border-blue-500/30 bg-[#1a1a1a]/90 p-4 text-white shadow-2xl backdrop-blur-xl transition-colors hover:bg-[#2a2a2a]/90 md:p-6"
                onClick={onOpenCart}
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.95 }}
                transition={{ type: "spring", stiffness: 380, damping: 26 }}
              >
                <ShoppingCart className="h-8 w-8 md:h-8 md:w-8" strokeWidth={2} />
                {cartCount > 0 ? (
                  <motion.span
                    className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-blue-500 text-[10px] font-bold text-white shadow-lg md:h-6 md:w-6 md:text-xs"
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{ type: "spring", stiffness: 380, damping: 24, delay: 0.34 }}
                  >
                    {cartCount}
                  </motion.span>
                ) : null}
              </motion.button>
            </motion.div>

            <motion.div
              className="pointer-events-auto"
              initial={{ opacity: 0, x: 18, y: 20 }}
              animate={{ opacity: 1, x: 0, y: 0 }}
              transition={{ type: "spring", stiffness: 320, damping: 28, delay: 0.12 }}
            >
              <motion.button
                type="button"
                aria-label="Моё местоположение"
                className={`${glassButtonClass} rounded-full p-3.5 md:p-5`}
                onClick={onGetLocation}
                {...iconButtonMotion}
              >
                <MapPin className="h-6 w-6 text-white md:h-7 md:w-7" strokeWidth={2} />
              </motion.button>
            </motion.div>
          </div>
        </div>
      </div>

      <div
        className="px-3 pt-1 md:px-6"
        style={{ paddingBottom: "max(0.75rem, env(safe-area-inset-bottom))" }}
      >
        <motion.nav
          className="rounded-[24px] border border-white/10 bg-[#1a1a1a]/95 px-2 py-1 shadow-2xl backdrop-blur-xl md:rounded-[32px] md:px-4 md:py-1.5"
          initial={{ y: 100 }}
          animate={{ y: 0 }}
          transition={{ type: "spring", stiffness: 300, damping: 30, delay: 0.42 }}
        >
          <div className="mx-auto flex max-w-2xl items-center justify-around">
            {navItems.map(({ key, label, Icon }) => {
              const isActive = currentView === key;
              return (
                <motion.button
                  key={key}
                  type="button"
                  className={`flex flex-col items-center gap-0.5 rounded-xl px-2 py-1 transition-colors md:gap-1 md:px-4 md:py-1.5 ${
                    isActive ? "text-blue-500" : "text-gray-400"
                  }`}
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  transition={{ type: "spring", stiffness: 380, damping: 26 }}
                  onClick={() => handleChangeView(key)}
                >
                  <Icon className="h-7 w-7 md:h-8 md:w-8" strokeWidth={2} />
                  <span className="text-xs font-semibold md:text-sm">{label}</span>
                </motion.button>
              );
            })}
          </div>
        </motion.nav>
      </div>
    </div>
  );
}

export default MapScreen;
