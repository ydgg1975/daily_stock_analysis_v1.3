import type React from 'react';
import { Languages } from 'lucide-react';
import { cn } from '../../utils/cn';
import { useI18n } from '../../contexts/UiLanguageContext';

type LanguageToggleVariant = 'default' | 'nav';

interface LanguageToggleProps {
  variant?: LanguageToggleVariant;
  collapsed?: boolean;
}

export const LanguageToggle: React.FC<LanguageToggleProps> = ({
  variant = 'default',
  collapsed = false,
}) => {
  const { language, toggleLanguage, t } = useI18n();
  const isNavVariant = variant === 'nav';

  return (
    <button
      type="button"
      onClick={toggleLanguage}
      className={cn(
        isNavVariant
          ? 'theme-panel-subtle flex h-11 w-full items-center gap-3 rounded-[var(--theme-button-radius)] px-3.5 text-sm text-secondary-text transition-all duration-200 ease-out hover:text-foreground'
          : 'theme-floating-control inline-flex h-10 items-center gap-2 rounded-xl px-3 text-sm text-secondary-text transition-all duration-200 ease-out hover:text-foreground',
        isNavVariant && collapsed ? 'justify-center px-2' : ''
      )}
      aria-label={t('language.toggle')}
      title={t('language.toggle')}
    >
      <Languages className={cn('shrink-0', isNavVariant ? 'h-5 w-5' : 'h-4 w-4')} />
      {isNavVariant ? (
        collapsed ? null : (
          <div className="min-w-0 text-left">
            <span className="block truncate text-[0.92rem] font-normal tracking-[-0.01em]">{t('nav.language')}</span>
            <span className="block truncate text-[10px] uppercase tracking-[0.16em] text-muted-text">
              {language === 'zh' ? t('language.zh') : t('language.en')}
            </span>
          </div>
        )
      ) : (
        <span className="hidden sm:inline">{language === 'zh' ? t('language.zh') : t('language.en')}</span>
      )}
    </button>
  );
};
