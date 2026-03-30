import type React from 'react';
import { cn } from '../../utils/cn';

interface ScrollAreaProps {
  children: React.ReactNode;
  className?: string;
  viewportClassName?: string;
  testId?: string;
  viewportRef?: React.Ref<HTMLDivElement>;
  onScroll?: React.UIEventHandler<HTMLDivElement>;
  onWheel?: React.WheelEventHandler<HTMLDivElement>;
}

export const ScrollArea: React.FC<ScrollAreaProps> = ({
  children,
  className,
  viewportClassName,
  testId,
  viewportRef,
  onScroll,
  onWheel,
}) => {
  return (
    <div className={cn('min-h-0 flex-1 overflow-hidden', className)}>
      <div
        ref={viewportRef}
        data-testid={testId}
        onScroll={onScroll}
        onWheel={onWheel}
        className={cn('h-full overflow-y-auto overscroll-contain custom-scrollbar [-webkit-overflow-scrolling:touch]', viewportClassName)}
      >
        {children}
      </div>
    </div>
  );
};
