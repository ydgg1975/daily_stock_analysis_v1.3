import type React from 'react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Check, Palette, Sparkles, SquareTerminal } from 'lucide-react';
import { cn } from '../../utils/cn';
import { useThemeStyle, type ThemeStylePreset } from './ThemeProvider';
import { useI18n } from '../../contexts/UiLanguageContext';

type ThemeToggleVariant = 'default' | 'nav';

const THEME_OPTIONS: Array<{
  value: ThemeStylePreset;
  labelKey: string;
  descriptionKey: string;
  icon: typeof Palette;
}> = [
  {
    value: 'terminal',
    labelKey: 'theme.terminal',
    descriptionKey: 'theme.terminalDesc',
    icon: SquareTerminal,
  },
  {
    value: 'cyber',
    labelKey: 'theme.cyber',
    descriptionKey: 'theme.cyberDesc',
    icon: Sparkles,
  },
  {
    value: 'hacker',
    labelKey: 'theme.hacker',
    descriptionKey: 'theme.hackerDesc',
    icon: Palette,
  },
];

function resolveThemeLabel(themeStyle: ThemeStylePreset, t: (key: string) => string) {
  return THEME_OPTIONS.find((item) => item.value === themeStyle)
    ? t(THEME_OPTIONS.find((item) => item.value === themeStyle)!.labelKey)
    : t('theme.terminal');
}

interface ThemeToggleProps {
  variant?: ThemeToggleVariant;
  collapsed?: boolean;
}

type PopoverPlacement = 'top' | 'bottom';

export const ThemeToggle: React.FC<ThemeToggleProps> = ({
  variant = 'default',
  collapsed = false,
}) => {
  const { t } = useI18n();
  const { themeStyle, setThemeStyle } = useThemeStyle();
  const [mounted, setMounted] = useState(false);
  const [uiState, setUiState] = useState<'open' | 'closed'>('closed');
  const containerRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const closeTimerRef = useRef<number | null>(null);

  const openPopover = useCallback(() => {
    if (closeTimerRef.current) {
      window.clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
    setMounted(true);
    window.requestAnimationFrame(() => {
      setUiState('open');
    });
  }, []);

  const closePopover = useCallback(() => {
    setUiState('closed');
    if (closeTimerRef.current) {
      window.clearTimeout(closeTimerRef.current);
    }
    closeTimerRef.current = window.setTimeout(() => {
      setMounted(false);
      closeTimerRef.current = null;
    }, 180);
  }, []);

  const updatePopoverPosition = useCallback(() => {
    if (!triggerRef.current || !panelRef.current) return;

    const triggerRect = triggerRef.current.getBoundingClientRect();
    const panelRect = panelRef.current?.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    const viewportPadding = 12;
    const edgeGap = 8;
    const targetMinWidth = variant === 'nav' ? 248 : 224;
    const estimatedWidth = panelRect?.width ?? targetMinWidth;
    const estimatedHeight = panelRect?.height ?? (variant === 'nav' ? 264 : 236);

    const alignLeft = variant === 'nav';
    const preferredLeft = alignLeft ? triggerRect.left : triggerRect.right - estimatedWidth;
    const clampedLeft = Math.min(
      Math.max(preferredLeft, viewportPadding),
      viewportWidth - estimatedWidth - viewportPadding,
    );

    const canOpenBottom = triggerRect.bottom + edgeGap + estimatedHeight <= viewportHeight - viewportPadding;
    const canOpenTop = triggerRect.top - edgeGap - estimatedHeight >= viewportPadding;
    const placement: PopoverPlacement = canOpenBottom || !canOpenTop ? 'bottom' : 'top';
    const rawTop = placement === 'bottom'
      ? triggerRect.bottom + edgeGap
      : triggerRect.top - estimatedHeight - edgeGap;
    const clampedTop = Math.min(
      Math.max(rawTop, viewportPadding),
      viewportHeight - estimatedHeight - viewportPadding,
    );

    panelRef.current.style.top = `${clampedTop}px`;
    panelRef.current.style.left = `${clampedLeft}px`;
    panelRef.current.style.minWidth = `${targetMinWidth}px`;
    panelRef.current.style.maxWidth = `${Math.min(estimatedWidth, viewportWidth - viewportPadding * 2)}px`;
    panelRef.current.style.transformOrigin = placement === 'top' ? 'bottom left' : 'top left';
    panelRef.current.style.visibility = 'visible';
  }, [variant]);

  useEffect(() => {
    if (!mounted) {
      return undefined;
    }

    const handlePointerDown = (event: MouseEvent | TouchEvent) => {
      const target = event.target as Node;
      if (
        containerRef.current?.contains(target)
        || panelRef.current?.contains(target)
      ) {
        return;
      }
      closePopover();
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        closePopover();
      }
    };

    const handleViewportChange = () => {
      updatePopoverPosition();
    };

    window.requestAnimationFrame(updatePopoverPosition);
    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('touchstart', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    window.addEventListener('resize', handleViewportChange);
    window.addEventListener('scroll', handleViewportChange, true);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('touchstart', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('resize', handleViewportChange);
      window.removeEventListener('scroll', handleViewportChange, true);
    };
  }, [closePopover, mounted, updatePopoverPosition]);

  useEffect(() => () => {
    if (closeTimerRef.current) {
      window.clearTimeout(closeTimerRef.current);
    }
  }, []);

  const activeTheme = themeStyle;
  const TriggerIcon = THEME_OPTIONS.find((item) => item.value === activeTheme)?.icon || SquareTerminal;
  const isNavVariant = variant === 'nav';

  return (
    <div className="relative" ref={containerRef}>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => {
          if (mounted) {
            closePopover();
          } else {
            openPopover();
          }
        }}
        data-state={mounted ? 'open' : 'closed'}
        className={cn(
          isNavVariant
            ? 'theme-panel-subtle group relative flex h-12 w-full select-none items-center gap-3 rounded-[1.35rem] px-4 text-sm text-secondary-text transition-all duration-200 ease-out hover:text-foreground data-[state=open]:text-foreground'
            : 'theme-floating-control inline-flex h-10 items-center gap-2 rounded-xl px-3 text-sm text-secondary-text transition-all duration-200 ease-out hover:text-foreground',
          isNavVariant && collapsed ? 'justify-center px-2' : ''
        )}
        aria-haspopup="menu"
        aria-expanded={mounted}
        aria-label={t('theme.label')}
      >
        <TriggerIcon className={cn('shrink-0', isNavVariant ? 'h-5 w-5' : 'h-4 w-4')} />
        {isNavVariant ? (
          collapsed ? null : (
            <div className="min-w-0">
              <span className="block truncate text-[1.02rem] font-medium">{t('nav.theme')}</span>
              <span className="block truncate text-[10px] uppercase tracking-[0.16em] text-muted-text">
                {resolveThemeLabel(activeTheme, t)}
              </span>
            </div>
          )
        ) : (
          <span className="hidden sm:inline">{resolveThemeLabel(activeTheme, t)}</span>
        )}
      </button>

      {mounted && typeof document !== 'undefined' ? createPortal(
        <div
          ref={panelRef}
          role="menu"
          aria-label={t('theme.menu')}
          data-state={uiState}
          className={cn(
            'theme-menu-panel fixed z-[160] w-max min-w-[14rem] overflow-hidden rounded-2xl p-1.5 transition-all duration-200 ease-out',
            uiState === 'open' ? 'opacity-100' : 'pointer-events-none opacity-0'
          )}
          style={{
            top: '0px',
            left: '0px',
            minWidth: `${isNavVariant ? 248 : 224}px`,
            maxWidth: '320px',
            transformOrigin: 'top left',
            visibility: 'hidden',
          }}
        >
          {THEME_OPTIONS.map(({ value, labelKey, descriptionKey, icon: Icon }) => {
            const isActive = activeTheme === value;
            return (
              <button
                key={value}
                type="button"
                role="menuitemradio"
                aria-checked={isActive}
                onClick={() => {
                  setThemeStyle(value);
                  closePopover();
                }}
                data-active={isActive}
                className={cn(
                  'theme-menu-option flex w-full items-start justify-between gap-3 rounded-xl px-3 py-2.5 text-left transition-all duration-200 ease-out',
                  isActive
                    ? 'text-foreground'
                    : 'text-secondary-text hover:text-foreground'
                )}
              >
                <span className="flex min-w-0 items-start gap-3">
                  <span className="theme-panel-subtle mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl">
                    <Icon className="h-4 w-4" />
                  </span>
                  <span className="min-w-0">
                    <span className="block text-sm font-medium">{t(labelKey)}</span>
                    <span className="mt-1 block text-xs leading-5 text-muted-text">{t(descriptionKey)}</span>
                  </span>
                </span>
                {isActive ? <Check className="theme-accent-icon h-4 w-4" /> : null}
              </button>
            );
          })}
        </div>,
        document.body
      ) : null}
    </div>
  );
};
