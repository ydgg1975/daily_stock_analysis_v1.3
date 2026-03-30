import type React from 'react';
import { useRef, useCallback, useEffect, useId } from 'react';
import { useI18n } from '../../contexts/UiLanguageContext';
import type { HistoryItem } from '../../types/analysis';
import { Badge, Button, ScrollArea } from '../common';
import { HistoryListItem } from './HistoryListItem';

interface HistoryListProps {
  items: HistoryItem[];
  isLoading: boolean;
  isLoadingMore: boolean;
  hasMore: boolean;
  selectedId?: number;  // 当前选中的历史记录 ID
  highlightedId?: number | null;
  selectedIds: Set<number>;
  isDeleting?: boolean;
  onItemClick: (recordId: number) => void;  // 点击记录的回调
  onLoadMore: () => void;
  onToggleItemSelection: (recordId: number) => void;
  onToggleSelectAll: () => void;
  onDeleteSelected: () => void;
  className?: string;
  embedded?: boolean;
}

/**
 * 历史记录列表组件 (升级版)
 * 使用新设计系统组件实现，支持批量选择和滚动加载
 */
export const HistoryList: React.FC<HistoryListProps> = ({
  items,
  isLoading,
  isLoadingMore,
  hasMore,
  selectedId,
  highlightedId,
  selectedIds,
  isDeleting = false,
  onItemClick,
  onLoadMore,
  onToggleItemSelection,
  onToggleSelectAll,
  onDeleteSelected,
  className = '',
  embedded = false,
}) => {
  const { t } = useI18n();
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const loadMoreTriggerRef = useRef<HTMLDivElement>(null);
  const selectAllRef = useRef<HTMLInputElement>(null);
  const selectAllId = useId();

  const selectedCount = items.filter((item) => selectedIds.has(item.id)).length;
  const allVisibleSelected = items.length > 0 && selectedCount === items.length;
  const someVisibleSelected = selectedCount > 0 && !allVisibleSelected;

  // 使用 IntersectionObserver 检测滚动到底部
  const handleObserver = useCallback(
    (entries: IntersectionObserverEntry[]) => {
      const target = entries[0];
      if (target.isIntersecting && hasMore && !isLoading && !isLoadingMore) {
        onLoadMore();
      }
    },
    [hasMore, isLoading, isLoadingMore, onLoadMore]
  );

  const handleScroll = useCallback<React.UIEventHandler<HTMLDivElement>>(
    (event) => {
      if (!hasMore || isLoading || isLoadingMore) {
        return;
      }
      const viewport = event.currentTarget;
      const remaining = viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight;
      if (remaining <= 96) {
        onLoadMore();
      }
    },
    [hasMore, isLoading, isLoadingMore, onLoadMore],
  );

  const handleAsideWheelCapture = useCallback<React.WheelEventHandler<HTMLElement>>((event) => {
    if (event.defaultPrevented) {
      return;
    }

    const viewport = scrollContainerRef.current;
    if (!viewport) {
      return;
    }

    const maxScrollTop = Math.max(0, viewport.scrollHeight - viewport.clientHeight);
    if (maxScrollTop <= 0) {
      event.preventDefault();
      event.stopPropagation();
      return;
    }

    const nextScrollTop = Math.min(
      maxScrollTop,
      Math.max(0, viewport.scrollTop + event.deltaY),
    );

    if (nextScrollTop !== viewport.scrollTop) {
      viewport.scrollTop = nextScrollTop;
    }

    event.preventDefault();
    event.stopPropagation();
  }, []);

  useEffect(() => {
    const trigger = loadMoreTriggerRef.current;
    const container = scrollContainerRef.current;
    if (!trigger || !container) return;

    const observer = new IntersectionObserver(handleObserver, {
      root: container,
      rootMargin: '20px',
      threshold: 0.1,
    });

    observer.observe(trigger);
    return () => observer.disconnect();
  }, [handleObserver]);

  useEffect(() => {
    const viewport = scrollContainerRef.current;
    if (!viewport) {
      return;
    }

    const handleWheel = (event: WheelEvent) => {
      if (event.defaultPrevented) {
        return;
      }
      if (!event.cancelable) {
        return;
      }

      const maxScrollTop = Math.max(0, viewport.scrollHeight - viewport.clientHeight);
      if (maxScrollTop <= 0) {
        event.preventDefault();
        event.stopPropagation();
        return;
      }

      const nextScrollTop = Math.min(
        maxScrollTop,
        Math.max(0, viewport.scrollTop + event.deltaY),
      );

      if (nextScrollTop !== viewport.scrollTop) {
        viewport.scrollTop = nextScrollTop;
      }

      // Always consume wheel inside history viewport to prevent page scroll chaining.
      event.preventDefault();
      event.stopPropagation();
    };

    const stopTouchBubble = (event: TouchEvent) => {
      event.stopPropagation();
    };

    viewport.addEventListener('wheel', handleWheel, { passive: false });
    viewport.addEventListener('touchstart', stopTouchBubble, { passive: true });
    viewport.addEventListener('touchmove', stopTouchBubble, { passive: true });

    return () => {
      viewport.removeEventListener('wheel', handleWheel);
      viewport.removeEventListener('touchstart', stopTouchBubble);
      viewport.removeEventListener('touchmove', stopTouchBubble);
    };
  }, []);

  useEffect(() => {
    if (selectAllRef.current) {
      selectAllRef.current.indeterminate = someVisibleSelected;
    }
  }, [someVisibleSelected]);

  useEffect(() => {
    if (!highlightedId) {
      return;
    }

    const viewport = scrollContainerRef.current;
    if (!viewport) {
      return;
    }

    const target = viewport.querySelector<HTMLElement>(`[data-history-item-id="${highlightedId}"]`);
    target?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [highlightedId, items]);

  const wrapperClass = embedded
    ? `theme-panel-solid min-h-0 h-full flex flex-1 flex-col overflow-hidden rounded-[1rem] ${className}`
    : `theme-panel-solid min-h-0 flex flex-1 flex-col overflow-hidden rounded-[1rem] ${className}`;

  return (
    <aside className={wrapperClass} onWheelCapture={handleAsideWheelCapture}>
      {embedded ? (
        <div className="theme-sidebar-divider flex items-center justify-between border-b px-3 py-2.5">
          <div className="flex items-center gap-2">
            <svg className="h-3.5 w-3.5 theme-accent-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <h2 className="text-xs font-semibold uppercase tracking-[0.16em] text-secondary-text">
              {t('history.title')}
            </h2>
          </div>
          {selectedCount > 0 ? (
            <Badge variant="info" size="sm" className="animate-in fade-in zoom-in duration-200">
              {t('history.selected', { count: selectedCount })}
            </Badge>
          ) : null}
        </div>
      ) : null}
      <ScrollArea
        viewportRef={scrollContainerRef}
        viewportClassName={embedded ? 'history-scroll-viewport h-full min-h-0 overflow-y-scroll px-1.5 pb-2' : 'history-scroll-viewport h-full min-h-0 p-4'}
        testId="home-history-list-scroll"
        onScroll={handleScroll}
      >
        <div className={embedded ? 'mb-2 space-y-2 px-2.5 pt-2.5' : 'mb-4 space-y-3'}>
          {!embedded ? (
            <div className="flex items-center justify-between gap-2">
              <h2 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-secondary-text">
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                {t('history.title')}
              </h2>
              {selectedCount > 0 && (
                <Badge variant="info" size="sm" className="animate-in fade-in zoom-in duration-200">
                  {t('history.selected', { count: selectedCount })}
                </Badge>
              )}
            </div>
          ) : null}

          {items.length > 0 && (
            <div className="flex items-center gap-2">
              <label
                className="flex flex-1 cursor-pointer items-center gap-2 rounded-lg px-2 py-0.5"
                htmlFor={selectAllId}
              >
                <input
                  id={selectAllId}
                  ref={selectAllRef}
                  type="checkbox"
                  checked={allVisibleSelected}
                  onChange={onToggleSelectAll}
                  disabled={isDeleting}
                  aria-label={t('history.currentLoaded')}
                  className="theme-checkbox"
                />
                <span className="select-none text-[11px] text-muted-text">{t('history.selectAllLoaded')}</span>
              </label>
              <Button
                variant="danger-subtle"
                size="sm"
                onClick={onDeleteSelected}
                disabled={selectedCount === 0 || isDeleting}
                isLoading={isDeleting}
                className="h-6 px-2 text-[9px] disabled:!border-transparent disabled:!bg-transparent"
              >
                {isDeleting ? t('history.deleting') : t('history.delete')}
              </Button>
            </div>
          )}
        </div>

        {isLoading ? (
          <div className="flex justify-center py-10">
            <div className="home-spinner h-6 w-6 animate-spin border-2" />
          </div>
        ) : items.length === 0 ? (
          <div className="space-y-3 py-12 text-center">
            <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-full bg-subtle text-muted-text/30">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div className="space-y-1">
              <p className="text-sm text-secondary-text">{t('history.emptyTitle')}</p>
              <p className="text-xs text-muted-text">{t('history.emptyBody')}</p>
            </div>
          </div>
        ) : (
          <div className={embedded ? 'space-y-1.5 px-2.5 pb-3' : 'space-y-2'}>
            {items.map((item) => (
              <HistoryListItem
                key={item.id}
                item={item}
                isViewing={selectedId === item.id}
                isHighlighted={highlightedId === item.id}
                isChecked={selectedIds.has(item.id)}
                isDeleting={isDeleting}
                onToggleChecked={onToggleItemSelection}
                onClick={onItemClick}
              />
            ))}

            <div ref={loadMoreTriggerRef} className="h-4" />
            
            {isLoadingMore && (
              <div className="flex justify-center py-4">
                <div className="home-spinner h-5 w-5 animate-spin border-2" />
              </div>
            )}

            {!hasMore && items.length > 0 && (
              <div className="text-center py-5">
                <div className="h-px bg-subtle w-full mb-3" />
                <span className="text-[10px] text-muted-text/50 uppercase tracking-[0.2em]">{t('history.bottom')}</span>
              </div>
            )}
          </div>
        )}
      </ScrollArea>
    </aside>
  );
};
