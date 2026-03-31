import type React from 'react';
import { useEffect, useState } from 'react';
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
  const [isMounted, setIsMounted] = useState(isOpen);
  const [uiState, setUiState] = useState<'open' | 'closed'>(isOpen ? 'open' : 'closed');

  useEffect(() => {
    if (isOpen) {
      window.requestAnimationFrame(() => {
        setIsMounted(true);
        window.requestAnimationFrame(() => setUiState('open'));
      });
      return;
    }
    if (!isMounted) {
      return;
    }
    queueMicrotask(() => setUiState('closed'));
    const timer = window.setTimeout(() => {
      setIsMounted(false);
    }, 180);
    return () => window.clearTimeout(timer);
  }, [isOpen, isMounted]);

  if (!isMounted) return null;

  const dialog = (
    <div
      className={`theme-overlay-backdrop fixed inset-0 z-50 flex items-center justify-center transition-opacity duration-200 ease-out ${
        uiState === 'open' ? 'opacity-100' : 'opacity-0'
      }`}
      data-state={uiState}
      onClick={onCancel}
    >
      <div
        className={`theme-modal-panel mx-4 w-full max-w-sm rounded-xl border p-6 transition-all duration-200 ease-out ${
          uiState === 'open'
            ? 'translate-y-0 scale-100 opacity-100'
            : 'translate-y-1.5 scale-[0.985] opacity-0'
        }`}
        data-state={uiState}
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
