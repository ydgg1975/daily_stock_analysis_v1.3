import type React from 'react';
import { createPortal } from 'react-dom';

interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  isDanger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * Generic confirmation dialog component.
 * Style is consistent with ChatPage.
 */
export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  isOpen,
  title,
  message,
  confirmText = '确定',
  cancelText = '取消',
  isDanger = false,
  onConfirm,
  onCancel,
}) => {
  if (!isOpen) return null;

  const dialog = (
    <div
      className="theme-overlay-backdrop fixed inset-0 z-50 flex items-center justify-center transition-all"
      onClick={onCancel}
    >
      <div
        className="theme-modal-panel mx-4 w-full max-w-sm rounded-xl border p-6 animate-in fade-in zoom-in duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="mb-2 text-lg font-medium text-foreground">{title}</h3>
        <p className="text-sm text-secondary-text mb-6 leading-relaxed">
          {message}
        </p>
        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-lg border border-[var(--border-muted)] bg-[var(--pill-bg)] px-4 py-2 text-sm font-medium text-secondary-text transition-colors hover:border-[var(--border-strong)] hover:bg-[var(--pill-active-bg)] hover:text-foreground"
          >
            {cancelText}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className={`rounded-lg px-4 py-2 text-sm font-medium text-foreground transition-colors ${
              isDanger
                ? 'border border-[hsl(var(--accent-danger-hsl)/0.64)] bg-[hsl(var(--accent-danger-hsl)/0.34)] hover:bg-[hsl(var(--accent-danger-hsl)/0.46)]'
                : 'border border-[hsl(var(--border-strong-hsl)/0.62)] bg-[var(--button-bg)] hover:bg-[var(--button-hover-bg)]'
            }`}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  );

  return createPortal(dialog, document.body);
};
