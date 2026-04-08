/**
 * SpaceX live refactor: preserves the existing confirmation flow and portal
 * behavior while restyling dialogs around restrained spectral typography,
 * lighter ghost actions, and a calmer modal surface.
 */
import type React from 'react';
import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { Button } from './Button';
import { useI18n } from '../../contexts/UiLanguageContext';

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

export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  isOpen,
  title,
  message,
  confirmText,
  cancelText,
  isDanger = false,
  onConfirm,
  onCancel,
}) => {
  const { t } = useI18n();
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

  useEffect(() => {
    if (!isMounted) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onCancel();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isMounted, onCancel]);

  if (!isMounted) return null;

  const dialog = (
    <div
      className={`confirm-dialog theme-overlay-backdrop fixed inset-0 z-50 flex items-center justify-center transition-opacity duration-200 ease-out ${
        uiState === 'open' ? 'opacity-100' : 'opacity-0'
      }`}
      data-state={uiState}
      onClick={onCancel}
    >
      <div
        className={`confirm-dialog__surface theme-modal-panel mx-4 w-full max-w-sm rounded-[var(--cohere-radius-medium)] border p-6 transition-all duration-200 ease-out ${
          uiState === 'open'
            ? 'translate-y-0 scale-100 opacity-100'
            : 'translate-y-1.5 scale-[0.985] opacity-0'
        }`}
        data-state={uiState}
        onClick={(e) => e.stopPropagation()}
      >
        <p className="confirm-dialog__eyebrow label-uppercase text-secondary-text">
          {isDanger ? t('common.confirmationRequired') : t('common.confirmAction')}
        </p>
        <h3 className="confirm-dialog__title text-[1.125rem] font-normal tracking-[-0.02em] text-foreground">{title}</h3>
        <p className="confirm-dialog__message mb-6 mt-2 text-sm leading-6 text-secondary-text">
          {message}
        </p>
        <div className="confirm-dialog__actions flex flex-wrap justify-end gap-2">
          <Button variant="ghost" size="sm" onClick={onCancel}>
            {cancelText ?? t('common.cancel')}
          </Button>
          <Button variant={isDanger ? 'danger-subtle' : 'primary'} size="sm" onClick={onConfirm}>
            {confirmText ?? t('common.confirm')}
          </Button>
        </div>
      </div>
    </div>
  );

  return createPortal(dialog, document.body);
};
