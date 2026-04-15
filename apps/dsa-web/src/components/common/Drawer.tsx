/**
 * SpaceX live refactor: preserves side-drawer mounting, focus escape, and body
 * scroll locking while simplifying the shell into a quieter translucent panel
 * with restrained header typography and lighter close controls.
 */
import type React from 'react';
import { useEffect, useCallback, useId, useRef, useState } from 'react';
import { cn } from '../../utils/cn';
import { useI18n } from '../../contexts/UiLanguageContext';

let activeDrawerCount = 0;
const BACKDROP_INTERACTION_GUARD_MS = 420;

interface DrawerProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  width?: string;
  zIndex?: number;
  side?: 'left' | 'right';
  closeOnBackdropClick?: boolean;
}

export const Drawer: React.FC<DrawerProps> = ({
  isOpen,
  onClose,
  title,
  children,
  width = 'max-w-2xl',
  zIndex = 50,
  side = 'right',
  closeOnBackdropClick = true,
}) => {
  const { t } = useI18n();
  const generatedId = useId();
  const [isMounted, setIsMounted] = useState(isOpen);
  const [uiState, setUiState] = useState<'open' | 'closed'>(isOpen ? 'open' : 'closed');
  const backdropGuardRef = useRef(isOpen);
  const backdropGuardTimerRef = useRef<number | null>(null);

  // Close the drawer when Escape is pressed.
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    },
    [onClose]
  );

  useEffect(() => {
    if (isOpen) {
      backdropGuardRef.current = true;
      if (backdropGuardTimerRef.current != null) {
        window.clearTimeout(backdropGuardTimerRef.current);
      }
      backdropGuardTimerRef.current = window.setTimeout(() => {
        backdropGuardRef.current = false;
        backdropGuardTimerRef.current = null;
      }, BACKDROP_INTERACTION_GUARD_MS);
      window.requestAnimationFrame(() => {
        setIsMounted(true);
        window.requestAnimationFrame(() => setUiState('open'));
      });
      return;
    }

    backdropGuardRef.current = false;
    if (backdropGuardTimerRef.current != null) {
      window.clearTimeout(backdropGuardTimerRef.current);
      backdropGuardTimerRef.current = null;
    }

    if (!isMounted) {
      return;
    }
    queueMicrotask(() => setUiState('closed'));
    const timer = window.setTimeout(() => {
      setIsMounted(false);
    }, 190);
    return () => window.clearTimeout(timer);
  }, [isOpen, isMounted]);

  useEffect(() => () => {
    if (backdropGuardTimerRef.current != null) {
      window.clearTimeout(backdropGuardTimerRef.current);
    }
  }, []);

  useEffect(() => {
    if (!isMounted) {
      return;
    }
    document.addEventListener('keydown', handleKeyDown);
    activeDrawerCount++;
    if (activeDrawerCount === 1) {
      document.body.style.overflow = 'hidden';
    }

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      activeDrawerCount--;
      if (activeDrawerCount === 0) {
        document.body.style.overflow = '';
      }
    };
  }, [isMounted, handleKeyDown]);

  const handleBackdropClick = useCallback(() => {
    if (!closeOnBackdropClick) {
      return;
    }
    if (backdropGuardRef.current) {
      return;
    }
    onClose();
  }, [closeOnBackdropClick, onClose]);

  if (!isMounted) return null;

  const titleId = title ? `drawer-title-${generatedId}` : undefined;
  const sidePositionClass = side === 'left' ? 'left-0 justify-start' : 'right-0 justify-end';
  const borderClass = side === 'left' ? 'border-r' : 'border-l';
  const panelStateClass = side === 'left'
    ? uiState === 'open'
      ? 'translate-x-0 opacity-100'
      : '-translate-x-full opacity-0'
    : uiState === 'open'
      ? 'translate-x-0 opacity-100'
      : 'translate-x-full opacity-0';

  return (
    <div className="fixed inset-0 overflow-hidden overscroll-contain" style={{ zIndex }} role="presentation">
      {/* Backdrop */}
      <div
        data-state={uiState}
        className={cn(
          'theme-overlay-backdrop absolute inset-0 transition-opacity duration-200 ease-out',
          uiState === 'open' ? 'pointer-events-auto opacity-100' : 'pointer-events-none opacity-0',
        )}
        onClick={handleBackdropClick}
      />

      <div className={cn('drawer__frame absolute inset-y-0 flex w-full', sidePositionClass, width)}>
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby={titleId}
          className={cn(
            'drawer__panel theme-modal-panel relative flex w-full flex-col transition-all duration-200 ease-out',
            borderClass,
            side === 'right' ? 'border-border/70' : 'border-border/70',
            panelStateClass,
          )}
          data-state={uiState}
        >
          <div className="drawer__header flex items-center justify-between border-b border-[var(--theme-panel-subtle-border)] px-4 py-3 sm:px-5 [padding-top:max(0.9rem,env(safe-area-inset-top))]">
            {title ? (
              <h2 id={titleId} className="drawer__title text-[11px] font-semibold uppercase tracking-[0.16em] text-secondary-text">
                {title}
              </h2>
            ) : <div />}
            <button
              type="button"
              onClick={onClose}
              className="drawer__close inline-flex h-9 w-9 items-center justify-center rounded-[var(--theme-button-radius)] border border-[var(--border-muted)] bg-[var(--overlay-hover)] text-secondary-text transition-colors hover:border-[var(--border-default)] hover:bg-[var(--overlay-selected)] hover:text-foreground"
              aria-label={t('common.closeDrawer')}
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div className="drawer__body flex h-full min-h-0 flex-1 flex-col overflow-y-auto overscroll-contain px-4 py-4 sm:px-5 sm:py-5 [padding-bottom:max(1rem,env(safe-area-inset-bottom))] [-webkit-overflow-scrolling:touch]">
            {children}
          </div>
        </div>
      </div>
    </div>
  );
};
