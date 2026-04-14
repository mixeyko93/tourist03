import type { PropsWithChildren } from "react";
import { motion } from "motion/react";

type PageMotionProps = PropsWithChildren<{
  className?: string;
}>;

export function PageMotion({ children, className = "" }: PageMotionProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
      className={className}
    >
      {children}
    </motion.div>
  );
}
