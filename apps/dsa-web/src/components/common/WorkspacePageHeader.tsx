import type React from 'react';
import { cn } from '../../utils/cn';

type WorkspacePageHeaderProps = {
  eyebrow?: React.ReactNode;
  title: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
  contentClassName?: string;
  titleClassName?: string;
  descriptionClassName?: string;
};

export const WorkspacePageHeader: React.FC<WorkspacePageHeaderProps> = ({
  eyebrow,
  title,
  description,
  actions,
  children,
  className,
  contentClassName,
  titleClassName,
  descriptionClassName,
}) => (
  <header className={cn('workspace-header-panel', className)}>
    <div className={cn('workspace-header-layout', contentClassName)}>
      <div className="workspace-header-copy">
        {eyebrow ? (
          <p className="text-[11px] uppercase tracking-[0.18em] text-muted-text">{eyebrow}</p>
        ) : null}
        <h1 className={cn('mt-2 text-xl font-semibold tracking-tight text-foreground md:text-2xl', titleClassName)}>
          {title}
        </h1>
        {description ? (
          <p className={cn('mt-2 text-sm leading-6 text-secondary-text', descriptionClassName)}>
            {description}
          </p>
        ) : null}
      </div>
      {actions ? (
        <div className="workspace-header-actions workspace-header-actions--end">
          {actions}
        </div>
      ) : null}
    </div>
    {children ? <div className="mt-4 space-y-4">{children}</div> : null}
  </header>
);
