/**
 * SpaceX live refactor: preserves labeling, validation, and password visibility
 * behavior while moving shared text inputs toward quieter ghost surfaces,
 * cleaner inline accessories, and theme-driven control typography.
 */
import type React from 'react';
import { useId, useState } from 'react';
import { Lock, Key } from 'lucide-react';
import { useI18n } from '../../contexts/UiLanguageContext';
import { cn } from '../../utils/cn';
import { EyeToggleIcon } from './EyeToggleIcon';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  hint?: string;
  error?: string;
  trailingAction?: React.ReactNode;
  /** Enables the built-in password visibility toggle. */
  allowTogglePassword?: boolean;
  /** Controls the leading icon style. */
  iconType?: 'password' | 'key' | 'none';
  /** Allows external visibility state control. */
  passwordVisible?: boolean;
  /** Notifies the parent when visibility changes in controlled mode. */
  onPasswordVisibleChange?: (visible: boolean) => void;
}

export const Input = ({ 
  label, 
  hint, 
  error, 
  className = '', 
  id, 
  trailingAction, 
  allowTogglePassword,
  iconType = 'none',
  passwordVisible,
  onPasswordVisibleChange,
  ...props 
}: InputProps) => {
  const { t } = useI18n();
  const generatedId = useId();
  const inputId = id ?? props.name ?? generatedId;
  const hintId = hint ? `${inputId}-hint` : undefined;
  const errorId = error ? `${inputId}-error` : undefined;
  const describedBy = [props['aria-describedby'], errorId ?? hintId].filter(Boolean).join(' ') || undefined;
  const ariaInvalid = props['aria-invalid'] ?? (error ? true : undefined);

  const [isPasswordVisible, setIsPasswordVisible] = useState(false);
  const isPasswordInput = props.type === 'password';
  const isVisibilityControlled = typeof passwordVisible === 'boolean';
  const visible = isVisibilityControlled ? passwordVisible : isPasswordVisible;
  const effectiveType = isPasswordInput && allowTogglePassword && visible ? 'text' : props.type;

  const renderLeadingIcon = () => {
    if (iconType === 'password') {
      return <Lock className="h-4 w-4 text-muted-text/55" />;
    }
    if (iconType === 'key') {
      return <Key className="h-4 w-4 text-muted-text/55" />;
    }
    return null;
  };

  const leadingIcon = renderLeadingIcon();
  const inputStyle = error
    ? {
      ...props.style,
      ['--input-surface-border-focus' as string]: 'hsla(var(--destructive), 0.4)',
      ['--input-surface-focus-ring' as string]: '0 0 0 4px hsla(var(--destructive), 0.1)',
    }
    : props.style;

  const defaultTrailingAction = isPasswordInput && allowTogglePassword ? (
    <button
      type="button"
      className={cn(
        'input-surface__toggle inline-flex h-8 w-8 items-center justify-center rounded-full border border-transparent bg-transparent transition-all duration-200 focus:outline-none focus:ring-2',
        visible
          ? 'text-foreground'
          : 'text-muted-text focus:ring-[var(--focus-ring)]'
      )}
      onClick={() => {
        const nextVisible = !visible;
        if (!isVisibilityControlled) {
          setIsPasswordVisible(nextVisible);
        }
        onPasswordVisibleChange?.(nextVisible);
      }}
      aria-label={visible ? t('common.hideContent') : t('common.showContent')}
      tabIndex={-1}
      title={visible ? t('common.hide') : t('common.show')}
    >
      <EyeToggleIcon visible={visible} />
    </button>
  ) : null;

  const finalTrailingAction = trailingAction || defaultTrailingAction;

  return (
    <div className="input-field flex flex-col">
      {label ? <label htmlFor={inputId} className="theme-field-label mb-2">{label}</label> : null}
      <div className="input-field__control relative flex items-center">
        {leadingIcon && (
          <div className="input-field__icon absolute left-3.5 z-10 pointer-events-none">
            {leadingIcon}
          </div>
        )}
        <input
          id={inputId}
          aria-describedby={describedBy}
          aria-invalid={ariaInvalid}
          style={inputStyle}
          className={cn(
            'input-surface input-focus-glow h-12 w-full rounded-[var(--theme-control-radius)] border bg-transparent px-4 text-sm transition-all',
            'focus:outline-none',
            error ? 'border-danger/30' : '',
            leadingIcon ? 'pl-10' : '',
            finalTrailingAction ? 'pr-12' : '',
            'disabled:cursor-not-allowed disabled:opacity-60',
            className,
          )}
          {...props}
          type={effectiveType}
        />
        {finalTrailingAction ? (
          <div className="input-field__trailing absolute inset-y-0 right-2 flex items-center">
            {finalTrailingAction}
          </div>
        ) : null}
      </div>
      {error ? (
        <p id={errorId} role="alert" className="mt-2 text-xs text-danger">
          {error}
        </p>
      ) : hint ? (
        <p id={hintId} className="mt-2 text-xs leading-5 text-secondary-text">
          {hint}
        </p>
      ) : null}
    </div>
  );
};
