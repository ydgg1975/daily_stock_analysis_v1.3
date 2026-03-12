import type React from 'react';
import { cn } from '../../utils/cn';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  hint?: string;
  error?: string;
}

export const Input = ({ label, hint, error, className = '', id, ...props }: InputProps) => {
  const inputId = id ?? props.name;

  return (
    <div className="flex flex-col">
      {label ? <label htmlFor={inputId} className="mb-2 text-sm font-medium text-foreground">{label}</label> : null}
      <input
        id={inputId}
        className={cn(
          'h-11 w-full rounded-xl border border-white/10 bg-card px-4 text-sm text-foreground shadow-soft-card transition-all',
          'placeholder:text-muted focus:outline-none focus:ring-4 focus:ring-cyan/15 focus:border-cyan/40',
          error ? 'border-danger/30 focus:border-danger/40 focus:ring-danger/10' : 'hover:border-white/18',
          className,
        )}
        {...props}
      />
      {error ? <p className="mt-2 text-xs text-danger">{error}</p> : hint ? <p className="mt-2 text-xs text-secondary">{hint}</p> : null}
    </div>
  );
};
