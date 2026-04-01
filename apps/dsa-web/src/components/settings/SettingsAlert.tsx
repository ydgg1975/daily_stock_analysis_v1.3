import type React from 'react';
import { SupportBanner } from '../common/SupportSurface';

interface SettingsAlertProps {
  title: string;
  message: string;
  variant?: 'error' | 'success' | 'warning';
  actionLabel?: string;
  onAction?: () => void;
  className?: string;
}

const variantTone: Record<NonNullable<SettingsAlertProps['variant']>, 'danger' | 'success' | 'warning'> = {
  error: 'danger',
  success: 'success',
  warning: 'warning',
};

export const SettingsAlert: React.FC<SettingsAlertProps> = ({
  title,
  message,
  variant = 'error',
  actionLabel,
  onAction,
  className = '',
}) => {
  return (
    <SupportBanner
      tone={variantTone[variant]}
      title={title}
      body={message}
      className={className}
      role="alert"
      actions={actionLabel && onAction ? (
        <button type="button" className="btn-secondary !px-3 !py-1.5 !text-xs" onClick={onAction}>
          {actionLabel}
        </button>
      ) : undefined}
    />
  );
};
