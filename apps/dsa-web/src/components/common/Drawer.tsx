import type React from 'react';
import { useEffect, useCallback } from 'react';
import { cn } from '../../utils/cn';

let activeDrawerCount = 0;

interface DrawerProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  width?: string;
  zIndex?: number;
  side?: 'left' | 'right';
}

/**
 * Side drawer component with terminal-inspired styling.
 */
export const Drawer: React.FC<DrawerProps> = ({
  isOpen,
  onClose,
  title,
  children,
  width = 'max-w-2xl',
  zIndex = 50,
  side = 'right',
}) => {
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
    }
  }, [isOpen, handleKeyDown]);

  if (!isOpen) return null;

  const titleId = title ? `drawer-title-${side}` : undefined;
  const sidePositionClass = side === 'left' ? 'left-0 justify-start' : 'right-0 justify-end';
  const borderClass = side === 'left' ? 'border-r' : 'border-l';

  return (
    <div className="fixed inset-0 overflow-hidden overscroll-contain" style={{ zIndex }} role="presentation">
      {/* Backdrop */}
      <div
        className="theme-overlay-backdrop absolute inset-0 transition-opacity duration-300"
        onClick={onClose}
      />

      <div className={cn('absolute inset-y-0 flex w-full', sidePositionClass, width)}>
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby={titleId}
          className={cn(
            'theme-modal-panel relative flex w-full flex-col',
            borderClass,
            side === 'right' ? 'border-border/70' : 'border-border/70',
            side === 'left' ? 'animate-slide-in-left' : 'animate-slide-in-right'
          )}
        >
          <div className="flex items-center justify-between border-b border-[var(--theme-panel-subtle-border)] px-6 py-4">
            {title ? (
              <div>
                <span className="label-uppercase">DETAIL VIEW</span>
                <h2 id={titleId} className="mt-1 text-lg font-semibold text-foreground">{title}</h2>
              </div>
            ) : <div />}
            <button
              type="button"
              onClick={onClose}
              className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-[var(--border-muted)] bg-[var(--pill-bg)] text-secondary-text transition-colors hover:border-[var(--border-strong)] hover:bg-[var(--pill-active-bg)] hover:text-foreground"
              aria-label="关闭抽屉"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div className="flex-1 overflow-y-auto overscroll-contain p-6 [-webkit-overflow-scrolling:touch]">
            {children}
          </div>
        </div>
      </div>
    </div>
  );
};
