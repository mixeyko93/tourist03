import type { PropsWithChildren } from "react";
import { motion } from "motion/react";

type PageMotionProps = PropsWithChildren<{
  className?: string;
  isReady?: boolean;
}>;

export function PageMotion({ children, className = "", isReady = true }: PageMotionProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={isReady ? { opacity: 1, y: 0 } : { opacity: 0, y: 20 }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      className={className}
    >
      {children}
    </motion.div>
  );
}
