import type { PropsWithChildren } from "react";
import { motion } from "motion/react";

type PageMotionProps = PropsWithChildren<{
  className?: string;
}>;

export function PageMotion({ children, className = "" }: PageMotionProps) {
  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className={className}>
      {children}
    </motion.div>
  );
}
