import type { PropsWithChildren } from "react";
import { AnimatePresence, motion } from "motion/react";

type ModalShellProps = PropsWithChildren<{
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
}>;

export function ModalShell({ open, onClose, title, description, children }: ModalShellProps) {
  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/55 p-4 backdrop-blur-md"
          onClick={onClose}
        >
          <motion.div
            initial={{ opacity: 0, y: 16, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.98 }}
            transition={{ duration: 0.2 }}
            className="w-full max-w-2xl rounded-3xl border border-border bg-card/92 shadow-2xl backdrop-blur-xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="border-b border-border px-6 py-5">
              <h2 className="text-xl font-semibold tracking-[-0.03em] text-foreground">{title}</h2>
              {description ? <p className="mt-1 text-sm text-muted-foreground">{description}</p> : null}
            </div>
            <div className="max-h-[90vh] overflow-y-auto px-6 py-6">{children}</div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
