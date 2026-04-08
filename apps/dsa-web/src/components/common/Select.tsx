/**
 * SpaceX live refactor: preserves the shared select API while aligning dropdown
 * controls with the same restrained input surface, uppercase field labels,
 * and minimal accessory treatment used across the updated frontend.
 */
import React, { useId } from 'react';
import { useI18n } from '../../contexts/UiLanguageContext';
import { cn } from '../../utils/cn';

interface SelectOption {
  value: string;
  label: string;
}

interface SelectProps {
  id?: string;
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  label?: string;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  searchable?: boolean;
  searchPlaceholder?: string;
  emptyText?: string;
}

export const Select: React.FC<SelectProps> = ({
  id,
  value,
  onChange,
  options,
  label,
  placeholder,
  disabled = false,
  className = '',
}) => {
  const { t } = useI18n();
  const selectId = useId();
  const resolvedId = id ?? selectId;
  const resolvedPlaceholder = placeholder ?? t('common.selectPlaceholder');

  return (
    <div className={cn('select-field flex flex-col', className)}>
      {label ? <label htmlFor={resolvedId} className="theme-field-label mb-2">{label}</label> : null}
      <div className="select-field__control relative">
        <select
          id={resolvedId}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          className={cn(
            'select-surface input-surface theme-focus-ring h-12 w-full appearance-none rounded-[var(--theme-control-radius)] border bg-transparent px-4 py-2.5 pr-10 text-sm text-foreground',
            'theme-focus-ring transition-all duration-200',
            disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer',
          )}
        >
          {resolvedPlaceholder && (
            <option value="" disabled>
              {resolvedPlaceholder}
            </option>
          )}
          {options.map((option) => (
            <option key={option.value} value={option.value} className="bg-[var(--surface-2)] text-foreground">
              {option.label}
            </option>
          ))}
        </select>

        {/* Dropdown arrow */}
        <div className="select-field__icon absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none">
          <svg
            className="h-4 w-4 text-secondary-text"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>
    </div>
  );
};
