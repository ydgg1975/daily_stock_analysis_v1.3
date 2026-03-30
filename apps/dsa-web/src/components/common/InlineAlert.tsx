import type React from 'react';
import { cn } from '../../utils/cn';

type InlineAlertVariant = 'info' | 'success' | 'warning' | 'danger';

interface InlineAlertProps {
  title?: string;
  message: React.ReactNode;
  variant?: InlineAlertVariant;
  action?: React.ReactNode;
  className?: string;
}

const variantStyles: Record<InlineAlertVariant, string> = {
  info: 'border-[hsl(var(--accent-primary-hsl)/0.28)] bg-[hsl(var(--accent-primary-hsl)/0.14)] text-[var(--accent-primary)]',
  success: 'border-[hsl(var(--accent-positive-hsl)/0.28)] bg-[hsl(var(--accent-positive-hsl)/0.14)] text-[var(--accent-positive)]',
  warning: 'border-[hsl(var(--accent-warning-hsl)/0.28)] bg-[hsl(var(--accent-warning-hsl)/0.14)] text-[var(--accent-warning)]',
  danger: 'border-[hsl(var(--accent-danger-hsl)/0.28)] bg-[hsl(var(--accent-danger-hsl)/0.14)] text-[var(--accent-danger)]',
};

export const InlineAlert: React.FC<InlineAlertProps> = ({
  title,
  message,
  variant = 'info',
  action,
  className = '',
}) => {
  return (
    <div className={cn('rounded-2xl border px-4 py-3 shadow-soft-card', variantStyles[variant], className)}>
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          {title ? <p className="text-sm font-semibold">{title}</p> : null}
          <div className={cn('text-sm', title ? 'mt-1 opacity-90' : 'opacity-90')}>{message}</div>
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
    </div>
  );
};
