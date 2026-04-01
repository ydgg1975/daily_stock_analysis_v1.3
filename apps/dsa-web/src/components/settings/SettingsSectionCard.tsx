import type React from 'react';
import { cn } from '../../utils/cn';

interface SettingsSectionCardProps {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  actionsClassName?: string;
}

export const SettingsSectionCard: React.FC<SettingsSectionCardProps> = ({
  title,
  description,
  actions,
  children,
  className = '',
  actionsClassName = '',
}) => {
  return (
    <div className={cn('rounded-[1.5rem] border settings-border bg-card p-5 shadow-soft-card-strong', className)}>
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 space-y-1">
          <h2 className="text-sm font-semibold tracking-tight text-foreground uppercase tracking-wider">{title}</h2>
          {description ? <p className="text-xs leading-6 text-muted-text">{description}</p> : null}
        </div>
        {actions ? <div className={cn('flex shrink-0 flex-wrap items-center gap-2 sm:justify-end', actionsClassName)}>{actions}</div> : null}
      </div>
      <div className="space-y-5">{children}</div>
    </div>
  );
};
