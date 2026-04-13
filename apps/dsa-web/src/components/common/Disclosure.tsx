import type React from 'react';
import { cn } from '../../utils/cn';

type DisclosureProps = {
  summary: React.ReactNode;
  children: React.ReactNode;
  defaultOpen?: boolean;
  className?: string;
  summaryClassName?: string;
  bodyClassName?: string;
};

export const Disclosure: React.FC<DisclosureProps> = ({
  summary,
  children,
  defaultOpen = false,
  className,
  summaryClassName,
  bodyClassName,
}) => (
  <details className={cn('product-disclosure', className)} open={defaultOpen}>
    <summary className={cn('product-disclosure__summary', summaryClassName)}>{summary}</summary>
    <div className={cn('product-disclosure__body', bodyClassName)}>{children}</div>
  </details>
);
