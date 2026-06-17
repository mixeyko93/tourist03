import { useEffect, useState } from "react";
import { ModalShell } from "./ModalShell";

type SensitiveChangeModalProps = {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  applyLabel?: string;
  loading?: boolean;
  loadingAction?: "confirm" | "apply" | null;
  commentRequired?: boolean;
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
  loadingAction = null,
  commentRequired = true,
  onClose,
  onConfirm,
  onApply,
}: SensitiveChangeModalProps) {
  const [comment, setComment] = useState("");
  const [commentError, setCommentError] = useState("");

  useEffect(() => {
    if (!open) {
      setComment("");
      setCommentError("");
    }
  }, [open]);

  const loadingText = loadingAction === "confirm" ? "Идёт отправка..." : loadingAction === "apply" ? "Сохранение..." : "Сохраняем...";

  const submitWithComment = (action: "confirm" | "apply") => {
    const trimmedComment = comment.trim();
    if (commentRequired && !trimmedComment) {
      setCommentError("Комментарий обязателен для этого изменения.");
      return;
    }
    setCommentError("");
    if (action === "confirm") {
      void onConfirm(trimmedComment);
      return;
    }
    void onApply(trimmedComment);
  };

  return (
    <ModalShell open={open} onClose={() => undefined} disableBackdropClose title={title} description={description}>
      <div className="space-y-5">
        <label className="space-y-2">
          <span className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Комментарий</span>
          <textarea
            className={`soft-input min-h-28 resize-none ${commentError ? "border-red-400/60" : ""}`.trim()}
            value={comment}
            onChange={(event) => {
              setComment(event.target.value);
              if (commentError) {
                setCommentError("");
              }
            }}
            placeholder="Коротко опишите цель изменений"
            aria-invalid={Boolean(commentError)}
          />
          {commentError ? <span className="block text-sm text-red-300">{commentError}</span> : null}
        </label>

        {loading ? (
          <div className="flex items-center gap-3 rounded-2xl border border-[#2F80ED]/20 bg-[#2F80ED]/10 px-4 py-3 text-sm text-foreground">
            <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-[#2F80ED]" />
            <span>{loadingText}</span>
          </div>
        ) : null}

        <div className="flex flex-col gap-3 border-t border-border pt-2 sm:flex-row sm:justify-end">
          <button type="button" className="soft-button justify-center px-4 py-2.5 text-sm" onClick={onClose} disabled={loading}>
            Отмена
          </button>
          <button
            type="button"
            className="soft-button justify-center border-[#2F80ED]/30 bg-[#2F80ED]/10 px-4 py-2.5 text-sm text-foreground hover:bg-[#2F80ED]/18"
            onClick={() => submitWithComment("confirm")}
            disabled={loading}
          >
            {confirmLabel}
          </button>
          <button type="button" className="brand-button justify-center px-5 py-2.5 text-sm" onClick={() => submitWithComment("apply")} disabled={loading}>
            {applyLabel}
          </button>
        </div>
      </div>
    </ModalShell>
  );
}
