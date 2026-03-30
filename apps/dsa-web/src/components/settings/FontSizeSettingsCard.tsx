import type React from 'react';
import { useI18n } from '../../contexts/UiLanguageContext';
import { useUiPreferences, type UiFontSize } from '../../contexts/UiPreferencesContext';
import { cn } from '../../utils/cn';

const OPTIONS: UiFontSize[] = ['xs', 's', 'm', 'l', 'xl'];

export const FontSizeSettingsCard: React.FC = () => {
  const { t } = useI18n();
  const { fontSize, setFontSize } = useUiPreferences();

  return (
    <div className="settings-surface rounded-[1rem] border settings-border px-4 py-4">
      <div className="mb-3">
        <p className="text-sm font-semibold text-foreground">{t('settings.fontSizeTitle')}</p>
        <p className="mt-1 text-xs leading-5 text-muted-text">{t('settings.fontSizeDesc')}</p>
      </div>
      <div className="grid grid-cols-5 gap-1.5">
        {OPTIONS.map((option) => (
          <button
            key={option}
            type="button"
            onClick={() => setFontSize(option)}
            className={cn(
              'rounded-lg border px-2 py-1.5 text-[11px] font-medium transition-colors',
              fontSize === option
                ? 'border-[var(--border-strong)] bg-[var(--pill-active-bg)] text-foreground shadow-[var(--glow-soft)]'
                : 'settings-border settings-surface-hover text-secondary-text hover:text-foreground',
            )}
            aria-pressed={fontSize === option}
          >
            {t(`settings.fontSize${option.toUpperCase()}`)}
          </button>
        ))}
      </div>
    </div>
  );
};
