import type React from 'react';
import { cn } from '../../utils/cn';

type SupportTone = 'default' | 'warning' | 'success' | 'danger';

interface SupportBaseProps {
  title?: React.ReactNode;
  body?: React.ReactNode;
  children?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
  titleClassName?: string;
  bodyClassName?: string;
  contentClassName?: string;
  actionsClassName?: string;
  role?: React.AriaRole;
}

interface SupportBannerProps extends SupportBaseProps {
  tone?: SupportTone;
}

interface SupportPanelProps extends SupportBaseProps {
  icon?: React.ReactNode;
  centered?: boolean;
}

const bannerToneClasses: Record<SupportTone, string> = {
  default: '',
  warning: 'theme-inline-banner--warning',
  success: 'theme-inline-banner--success',
  danger: 'theme-inline-banner--danger',
};

export const SupportBanner: React.FC<SupportBannerProps> = ({
  title,
  body,
  children,
  actions,
  tone = 'default',
  className,
  titleClassName,
  bodyClassName,
  contentClassName,
  actionsClassName,
  role,
}) => (
  <div className={cn('theme-inline-banner rounded-[var(--cohere-radius-medium)] px-4 py-4', bannerToneClasses[tone], className)} role={role}>
    {title ? <p className={cn('theme-inline-banner-title text-[0.98rem] font-normal tracking-[-0.01em]', titleClassName)}>{title}</p> : null}
    {body ? (
      <div className={cn(title ? 'mt-1.5' : '', 'text-sm leading-6 opacity-90', bodyClassName)}>
        {body}
      </div>
    ) : null}
    {children ? <div className={cn(title || body ? 'mt-3' : '', contentClassName)}>{children}</div> : null}
    {actions ? <div className={cn('mt-3 flex flex-wrap items-center gap-2', actionsClassName)}>{actions}</div> : null}
  </div>
);

export const SupportPanel: React.FC<SupportPanelProps> = ({
  title,
  body,
  children,
  actions,
  icon,
  centered = false,
  className,
  titleClassName,
  bodyClassName,
  contentClassName,
  actionsClassName,
  role,
}) => (
  <div
    className={cn(
      'theme-panel-subtle rounded-[var(--cohere-radius-medium)] px-4 py-4',
      centered && 'text-center',
      className,
    )}
    role={role}
  >
    {icon ? <div className={cn(centered && 'mx-auto')}>{icon}</div> : null}
    {title ? (
      <p className={cn(icon ? 'mt-4' : '', 'text-[1rem] font-normal tracking-[-0.01em] text-foreground', titleClassName)}>
        {title}
      </p>
    ) : null}
    {body ? (
      <div className={cn(title ? 'mt-1.5' : '', 'text-sm leading-6 text-muted-text', bodyClassName)}>
        {body}
      </div>
    ) : null}
    {children ? <div className={cn(title || body ? 'mt-3' : '', contentClassName)}>{children}</div> : null}
    {actions ? (
      <div className={cn('mt-3 flex flex-wrap items-center gap-2', centered && 'justify-center', actionsClassName)}>
        {actions}
      </div>
    ) : null}
  </div>
);
