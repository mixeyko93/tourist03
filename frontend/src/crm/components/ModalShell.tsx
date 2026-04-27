import { type PropsWithChildren, useEffect } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "motion/react";

type ModalShellProps = PropsWithChildren<{
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  disableBackdropClose?: boolean;
  panelClassName?: string;
  bodyClassName?: string;
}>;

export function ModalShell({ open, onClose, title, description, disableBackdropClose = false, panelClassName = "", bodyClassName = "", children }: ModalShellProps) {
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = prev; };
  }, [open]);

  if (typeof document === "undefined") {
    return null;
  }

  return createPortal(
    <AnimatePresence>
      {open ? (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-0 backdrop-blur-md dark:bg-black/55 sm:items-center sm:p-4 lg:left-[var(--crm-shell-offset,0px)] lg:top-16"
onClick={() => {
            if (!disableBackdropClose) {
              onClose();
            }
          }}
        >
          <motion.div
            initial={{ opacity: 0, y: 16, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.98 }}
            transition={{ duration: 0.2 }}
            className={`flex max-h-[95dvh] w-full max-w-2xl flex-col overflow-hidden rounded-t-3xl border border-border bg-white/96 shadow-2xl backdrop-blur-xl dark:bg-card/92 sm:rounded-3xl ${panelClassName}`.trim()}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="border-b border-border px-5 py-4 sm:px-6 sm:py-5">
              <h2 className="text-xl font-semibold tracking-[-0.03em] text-foreground">{title}</h2>
              {description ? <p className="mt-1 text-sm text-muted-foreground">{description}</p> : null}
            </div>
            <div className={`min-h-0 flex-1 overflow-y-auto px-5 py-5 pb-[max(1.25rem,env(safe-area-inset-bottom))] sm:px-6 sm:py-6 ${bodyClassName}`.trim()}>
              {children}
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>,
    document.body,
  );
}
