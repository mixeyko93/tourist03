import { useEffect, useState } from "react";
import { ModalShell } from "./ModalShell";

type SensitiveChangeModalProps = {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  applyLabel?: string;
  loading?: boolean;
  onClose: () => void;
  onConfirm: (comment: string) => Promise<void> | void;
  onApply: (comment: string) => Promise<void> | void;
};

export function SensitiveChangeModal({
  open,
  title,
  description,
  confirmLabel = "Отправить на подтверждение",
  applyLabel = "Применить под ответственность",
  loading = false,
  onClose,
  onConfirm,
  onApply,
}: SensitiveChangeModalProps) {
  const [comment, setComment] = useState("");

  useEffect(() => {
    if (!open) {
      setComment("");
    }
  }, [open]);

  return (
    <ModalShell open={open} onClose={() => !loading && onClose()} title={title} description={description}>
      <div className="space-y-5">
        <label className="space-y-2">
          <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Комментарий</span>
          <textarea
            className="soft-input min-h-28 resize-none"
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            placeholder="Коротко опишите цель изменений"
          />
        </label>

        <div className="flex flex-col gap-3 border-t border-border pt-2 sm:flex-row sm:justify-end">
          <button type="button" className="soft-button justify-center px-4 py-2.5 text-sm" onClick={onClose} disabled={loading}>
            Отмена
          </button>
          <button
            type="button"
            className="soft-button justify-center border-[#E5D3B3]/30 bg-[#E5D3B3]/10 px-4 py-2.5 text-sm text-foreground hover:bg-[#E5D3B3]/18"
            onClick={() => void onConfirm(comment)}
            disabled={loading}
          >
            {loading ? "Сохраняем..." : confirmLabel}
          </button>
          <button type="button" className="brand-button justify-center px-5 py-2.5 text-sm" onClick={() => void onApply(comment)} disabled={loading}>
            {loading ? "Сохраняем..." : applyLabel}
          </button>
        </div>
      </div>
    </ModalShell>
  );
}
