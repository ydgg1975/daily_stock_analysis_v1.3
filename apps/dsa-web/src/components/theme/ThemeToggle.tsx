import type React from 'react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Check, MoonStar } from 'lucide-react';
import { cn } from '../../utils/cn';
import { useThemeStyle } from './ThemeProvider';
import { useI18n } from '../../contexts/UiLanguageContext';

type ThemeToggleVariant = 'default' | 'nav';

interface ThemeToggleProps {
  variant?: ThemeToggleVariant;
  collapsed?: boolean;
}

export const ThemeToggle: React.FC<ThemeToggleProps> = ({
  variant = 'default',
  collapsed = false,
}) => {
  const { t } = useI18n();
  const { themeStyle, setThemeStyle } = useThemeStyle();
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);

  const close = useCallback(() => setOpen(false), []);

  useEffect(() => {
    if (!open) {
      return undefined;
    }

    const onPointerDown = (event: MouseEvent) => {
      const target = event.target as Node;
      if (triggerRef.current?.contains(target) || panelRef.current?.contains(target)) {
        return;
      }
      close();
    };

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        close();
      }
    };

    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [close, open]);

  useEffect(() => {
    if (!open || !triggerRef.current || !panelRef.current) {
      return;
    }

    const triggerRect = triggerRef.current.getBoundingClientRect();
    const panel = panelRef.current;
    const top = triggerRect.bottom + 8;
    const left = Math.max(12, Math.min(triggerRect.right - 248, window.innerWidth - 260));
    panel.style.top = `${top}px`;
    panel.style.left = `${left}px`;
  }, [open]);

  return (
    <div className="relative">
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen((current) => !current)}
        className={cn(
          variant === 'nav'
            ? 'shell-header-action'
            : 'theme-floating-control inline-flex min-h-[40px] items-center gap-2 rounded-[var(--theme-button-radius)] border px-4 text-[0.72rem] font-bold uppercase tracking-[0.16em] text-foreground',
          collapsed ? 'px-2' : '',
        )}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={t('theme.label')}
      >
        <MoonStar className="h-4 w-4" />
        {collapsed ? null : (
          <span>{t('theme.spacex')}</span>
        )}
      </button>

      {open && typeof document !== 'undefined'
        ? createPortal(
            <div
              ref={panelRef}
              role="menu"
              aria-label={t('theme.menu')}
              className="theme-menu-panel fixed z-[160] min-w-[15.5rem] rounded-[var(--theme-panel-radius-md)] border p-2"
            >
              <button
                type="button"
                role="menuitemradio"
                aria-checked="true"
                onClick={() => {
                  setThemeStyle(themeStyle);
                  close();
                }}
                className="theme-menu-option flex w-full items-start justify-between gap-3 rounded-[var(--theme-control-radius)] px-3 py-3 text-left"
              >
                <div className="min-w-0">
                  <span className="block text-[0.74rem] font-bold uppercase tracking-[0.16em] text-foreground">
                    {t('theme.spacex')}
                  </span>
                  <span className="mt-1 block text-[0.74rem] leading-6 text-secondary-text">
                    {t('theme.spacexDesc')}
                  </span>
                </div>
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-foreground" />
              </button>
            </div>,
            document.body,
          )
        : null}
    </div>
  );
};

export default ThemeToggle;
