import type React from 'react';
import { cn } from '../../utils/cn';

interface CardProps {
  title?: string;
  subtitle?: string;
  children: React.ReactNode;
  className?: string;
  variant?: 'default' | 'bordered' | 'gradient';
  hoverable?: boolean;
  padding?: 'none' | 'sm' | 'md' | 'lg';
}

/**
 * Card component aligned to the shared product design system.
 */
export const Card: React.FC<CardProps> = ({
  title,
  subtitle,
  children,
  className = '',
  variant = 'default',
  hoverable = false,
  padding = 'md',
}) => {
  const paddingStyles = {
    none: '',
    sm: 'p-4 md:p-5',
    md: 'p-5 md:p-6',
    lg: 'p-6 md:p-7',
  };

  const variantStyles = {
    default: 'theme-panel-solid',
    bordered: 'theme-panel-subtle',
    gradient: 'theme-panel-band',
  };

  const hoverStyles = hoverable ? 'theme-card-hover cursor-pointer' : '';

  return (
    <div
      className={cn(
        'theme-card-surface rounded-[var(--theme-panel-radius-lg)]',
        variantStyles[variant],
        hoverStyles,
        paddingStyles[padding],
        className,
      )}
    >
      {(title || subtitle) && (
        <div className="mb-4 space-y-1.5">
          {subtitle ? <span className="label-uppercase">{subtitle}</span> : null}
          {title ? <h3 className="text-[1.125rem] font-normal tracking-[-0.02em] text-foreground md:text-[1.25rem]">{title}</h3> : null}
        </div>
      )}
      {children}
    </div>
  );
};
