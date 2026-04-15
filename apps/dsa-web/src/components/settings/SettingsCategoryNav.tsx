import type React from 'react';
import { useI18n } from '../../contexts/UiLanguageContext';
import { getCategoryTitle } from '../../utils/systemConfigI18n';
import type { SystemConfigCategorySchema, SystemConfigItem } from '../../types/systemConfig';
import { cn } from '../../utils/cn';

interface SettingsCategoryNavProps {
  categories: SystemConfigCategorySchema[];
  itemsByCategory: Record<string, SystemConfigItem[]>;
  activeCategory: string;
  onSelect: (category: string) => void;
  disabled?: boolean;
  hideHeader?: boolean;
}

export const SettingsCategoryNav: React.FC<SettingsCategoryNavProps> = ({
  categories,
  itemsByCategory,
  activeCategory,
  onSelect,
  disabled = false,
  hideHeader = false,
}) => {
  const { language, t } = useI18n();
  return (
    <div className="flex h-full flex-col overflow-hidden rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/30">
      {!hideHeader ? (
        <div className="border-b border-[var(--theme-panel-subtle-border)] px-4 py-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-secondary-text">{t('settings.categoriesTitle')}</p>
        </div>
      ) : null}

      <div className="flex-1 overflow-y-auto py-2">
        {categories.map((category) => {
          const isActive = category.category === activeCategory;
          const count = (itemsByCategory[category.category] || []).length;
          const title = getCategoryTitle(language, category.category, category.title);

          return (
            <button
              key={category.category}
              type="button"
              className={cn(
                'w-full flex items-center justify-between border-l-[3px] border-y-0 border-r-0 px-4 py-2.5 text-left transition-colors bg-transparent',
                isActive
                  ? 'border-l-[var(--accent-primary)] bg-[var(--overlay-selected)]'
                  : 'border-l-transparent hover:border-l-[var(--border-muted)] hover:bg-[var(--overlay-hover)]',
                disabled ? 'pointer-events-none opacity-60' : '',
              )}
              onClick={() => {
                if (disabled) {
                  return;
                }
                onSelect(category.category);
              }}
              disabled={disabled}
            >
              <div className="min-w-0 flex-1">
                <p className={cn('text-[12px] font-semibold tracking-wide uppercase', isActive ? 'text-foreground' : 'text-secondary-text')}>
                  {title}
                </p>
              </div>
              <span className="text-[10px] font-mono text-muted-text ml-3">
                {count}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
};
