export const windowOverlayMotion = {
  initial: { opacity: 0 },
  animate: { opacity: 1 },
  exit: { opacity: 0 },
  transition: {
    duration: 0.22,
    ease: [0.22, 1, 0.36, 1] as const,
  },
};

export const windowCardMotion = {
  initial: { opacity: 0, y: 28, scale: 0.96 },
  animate: { opacity: 1, y: 0, scale: 1 },
  exit: { opacity: 0, y: 20, scale: 0.96 },
  transition: {
    type: "spring" as const,
    stiffness: 280,
    damping: 28,
  },
};
