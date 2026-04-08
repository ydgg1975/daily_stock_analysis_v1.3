/**
 * SpaceX live refactor: preserves page-range behavior while reducing pagination
 * controls to compact spectral chips with quieter inactive states and clearer
 * uppercase labeling consistent with the rest of the shell.
 */
import type React from 'react';
import { cn } from '../../utils/cn';

interface PageButtonProps {
  page: number | string;
  isActive?: boolean;
  disabled?: boolean;
  onClick?: () => void;
  children?: React.ReactNode;
}

const PageButton: React.FC<PageButtonProps> = ({ page, isActive, disabled, onClick, children }) => {
  const isEllipsis = page === '...';

  if (isEllipsis) {
    return <span className="pagination__ellipsis">...</span>;
  }

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        'pagination__button',
        'inline-flex h-10 min-w-[2.75rem] items-center justify-center rounded-[var(--theme-button-radius)] border px-3 text-[0.76rem] font-normal uppercase tracking-[0.14em] transition-all duration-200',
        isActive
          ? 'border-[var(--border-selected)] bg-[var(--overlay-selected)] text-foreground'
          : 'border-[var(--theme-panel-subtle-border)] bg-transparent text-secondary-text hover:border-[var(--border-default)] hover:bg-[var(--overlay-hover)] hover:text-foreground',
        disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer',
      )}
    >
      {children || page}
    </button>
  );
};

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  className?: string;
}

export const Pagination: React.FC<PaginationProps> = ({
  currentPage,
  totalPages,
  onPageChange,
  className = '',
}) => {
  if (totalPages <= 1) return null;

  // Build the page list with ellipsis placeholders.
  const getPageNumbers = (): (number | string)[] => {
    const pages: (number | string)[] = [];
    const delta = 2;

    for (let i = 1; i <= totalPages; i++) {
      if (
        i === 1 ||
        i === totalPages ||
        (i >= currentPage - delta && i <= currentPage + delta)
      ) {
        pages.push(i);
      } else if (pages[pages.length - 1] !== '...') {
        pages.push('...');
      }
    }

    return pages;
  };

  return (
    <div className={cn('pagination flex items-center justify-center gap-2', className)}>
      {/* Previous page */}
      <PageButton
        page="prev"
        disabled={currentPage === 1}
        onClick={() => onPageChange(currentPage - 1)}
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
      </PageButton>

      {/* Page numbers */}
      {getPageNumbers().map((page, index) => (
        <PageButton
          key={`${page}-${index}`}
          page={page}
          isActive={page === currentPage}
          onClick={() => typeof page === 'number' && onPageChange(page)}
        />
      ))}

      {/* Next page */}
      <PageButton
        page="next"
        disabled={currentPage === totalPages}
        onClick={() => onPageChange(currentPage + 1)}
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      </PageButton>
    </div>
  );
};
