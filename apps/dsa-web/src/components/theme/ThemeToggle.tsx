import type React from 'react';
import { useEffect, useRef, useState } from 'react';
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

export const ThemeToggle: React.FC<ThemeToggleProps> = ({
  variant = 'default',
  collapsed = false,
}) => {
  const { t } = useI18n();
  const { themeStyle, setThemeStyle } = useThemeStyle();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) {
      return undefined;
    }

    const handlePointerDown = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };

    document.addEventListener('mousedown', handlePointerDown);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
    };
  }, [open]);

  const activeTheme = themeStyle;
  const TriggerIcon = THEME_OPTIONS.find((item) => item.value === activeTheme)?.icon || SquareTerminal;
  const isNavVariant = variant === 'nav';

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        data-state={open ? 'open' : 'closed'}
        className={cn(
          isNavVariant
            ? 'theme-panel-subtle group relative flex h-12 w-full select-none items-center gap-3 rounded-[1.35rem] px-4 text-sm text-secondary-text transition-all duration-200 ease-out hover:text-foreground data-[state=open]:text-foreground'
            : 'theme-floating-control inline-flex h-10 items-center gap-2 rounded-xl px-3 text-sm text-secondary-text transition-all duration-200 ease-out hover:text-foreground',
          isNavVariant && collapsed ? 'justify-center px-2' : ''
        )}
        aria-haspopup="menu"
        aria-expanded={open}
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

      {open ? (
        <div
          role="menu"
          aria-label={t('theme.menu')}
          className={cn(
            'theme-menu-panel z-[100] min-w-[14rem] overflow-hidden rounded-2xl p-1.5',
            isNavVariant
              ? 'absolute bottom-full left-0 mb-2 w-max min-w-[15rem]'
              : 'absolute right-0 mt-2'
          )}
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
                  setOpen(false);
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
        </div>
      ) : null}
    </div>
  );
};
