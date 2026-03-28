import React from 'react';
import { cn } from '../../utils/cn';

type BadgeVariant = 'default' | 'success' | 'warning' | 'danger' | 'info' | 'history';

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  size?: 'sm' | 'md';
  glow?: boolean;
  className?: string;
}

const variantStyles: Record<BadgeVariant, string> = {
  default: 'border-white/8 bg-white/[0.035] text-secondary-text',
  success: 'border-emerald-400/16 bg-emerald-400/[0.08] text-emerald-200',
  warning: 'border-amber-300/16 bg-amber-300/[0.08] text-amber-100',
  danger: 'border-rose-400/16 bg-rose-400/[0.08] text-rose-200',
  info: 'border-cyan/14 bg-cyan/[0.08] text-cyan-100',
  history: 'border-violet-400/14 bg-violet-400/[0.08] text-violet-100',
};

const glowStyles: Record<BadgeVariant, string> = {
  default: 'ring-1 ring-white/6',
  success: 'ring-1 ring-emerald-400/10',
  warning: 'ring-1 ring-amber-300/10',
  danger: 'ring-1 ring-rose-400/10',
  info: 'ring-1 ring-cyan/10',
  history: 'ring-1 ring-violet-400/10',
};

/**
 * Badge component with multiple variants and optional glow styling.
 */
export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'default',
  size = 'sm',
  glow = false,
  className = '',
}) => {
  const sizeStyles = size === 'sm' ? 'min-h-6 px-2.5 py-0.5 text-[11px]' : 'min-h-7 px-3 py-1 text-sm';

  return (
    <span
      className={cn(
        'inline-flex items-center justify-center gap-1 rounded-full border font-medium leading-none backdrop-blur-sm',
        sizeStyles,
        variantStyles[variant],
        glow && glowStyles[variant],
        className,
      )}
    >
      {children}
    </span>
  );
};
