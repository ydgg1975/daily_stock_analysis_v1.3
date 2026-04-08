import type React from 'react';
import { useRef, useCallback, useEffect, useId, useState } from 'react';
import { useI18n } from '../../contexts/UiLanguageContext';
import type { HistoryItem } from '../../types/analysis';
import { Button, ScrollArea } from '../common';
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
  const [manageMode, setManageMode] = useState(false);
  const panelRef = useRef<HTMLElement>(null);
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

  const applyWheelScroll = useCallback((viewport: HTMLDivElement | null, deltaY: number): boolean => {
    if (!viewport) {
      return false;
    }

    const maxScrollTop = Math.max(0, viewport.scrollHeight - viewport.clientHeight);
    if (maxScrollTop <= 0) {
      return true;
    }

    const nextScrollTop = Math.min(
      maxScrollTop,
      Math.max(0, viewport.scrollTop + deltaY),
    );

    if (nextScrollTop !== viewport.scrollTop) {
      viewport.scrollTop = nextScrollTop;
    }

    return true;
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
    const panel = panelRef.current;
    if (!viewport) {
      return;
    }

    const handleWheel = (event: WheelEvent) => {
      if (event.defaultPrevented || !applyWheelScroll(viewport, event.deltaY)) {
        return;
      }

      event.preventDefault();
      event.stopPropagation();
    };

    const stopTouchBubble = (event: TouchEvent) => {
      event.stopPropagation();
    };

    panel?.addEventListener('wheel', handleWheel, { passive: false });
    viewport.addEventListener('wheel', handleWheel, { passive: false });
    viewport.addEventListener('touchstart', stopTouchBubble, { passive: true });
    viewport.addEventListener('touchmove', stopTouchBubble, { passive: true });

    return () => {
      panel?.removeEventListener('wheel', handleWheel);
      viewport.removeEventListener('wheel', handleWheel);
      viewport.removeEventListener('touchstart', stopTouchBubble);
      viewport.removeEventListener('touchmove', stopTouchBubble);
    };
  }, [applyWheelScroll]);

  useEffect(() => {
    if (selectAllRef.current) {
      selectAllRef.current.indeterminate = someVisibleSelected;
    }
  }, [someVisibleSelected]);

  useEffect(() => {
    if (selectedCount === 0 && !isDeleting) {
      selectAllRef.current?.removeAttribute('aria-busy');
    }
  }, [isDeleting, selectedCount]);

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
    ? `history-archive-panel min-h-0 h-full flex flex-1 flex-col overflow-hidden ${className}`
    : `history-archive-panel min-h-0 flex flex-1 flex-col overflow-hidden ${className}`;

  return (
    <aside
      ref={panelRef}
      className={wrapperClass}
      data-embedded={embedded ? 'true' : 'false'}
    >
      <div className="history-archive-panel__header">
        <div>
          <p className="history-archive-panel__eyebrow">{t('shell.archiveEyebrow')}</p>
          <h2 className="history-archive-panel__title">{t('history.title')}</h2>
        </div>
        <div className="history-archive-panel__actions">
          {manageMode && selectedCount > 0 ? (
            <span className="history-archive-panel__count">
              {t('history.selected', { count: selectedCount })}
            </span>
          ) : null}
          {items.length > 0 ? (
            <button
              type="button"
              onClick={() => setManageMode((current) => !current)}
              className="history-archive-panel__utility"
            >
              {manageMode ? t('history.done') : t('history.manage')}
            </button>
          ) : null}
        </div>
      </div>
      <ScrollArea
        viewportRef={scrollContainerRef}
        viewportClassName={embedded
          ? 'history-scroll-viewport history-scroll-viewport--archive h-full min-h-0 overflow-y-scroll px-0 pb-2'
          : 'history-scroll-viewport history-scroll-viewport--archive h-full min-h-0 px-0 pb-2'}
        testId="home-history-list-scroll"
        onScroll={handleScroll}
      >
        <div className="history-archive-panel__body">
          {manageMode && items.length > 0 ? (
            <div className="history-archive-panel__manage">
              <label
                className="history-archive-panel__select-all"
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
                <span>{t('history.selectAllLoaded')}</span>
              </label>
              <Button
                variant="danger-subtle"
                size="sm"
                onClick={onDeleteSelected}
                disabled={selectedCount === 0 || isDeleting}
                isLoading={isDeleting}
                className="history-archive-panel__delete"
              >
                {isDeleting ? t('history.deleting') : t('history.delete')}
              </Button>
            </div>
          ) : null}

          {items.length > 0 ? (
            <p className="history-archive-panel__caption">
              {t('history.archiveHint')}
            </p>
          ) : null}
        </div>

        {isLoading ? (
          <div className="history-archive-state">
            <div className="history-archive-state__pulse" />
            <p>{t('history.loading')}</p>
          </div>
        ) : items.length === 0 ? (
          <div className="history-archive-state">
            <p className="history-archive-state__title">{t('history.emptyTitle')}</p>
            <p>{t('history.emptyBody')}</p>
          </div>
        ) : (
          <div className="history-archive-list">
            {items.map((item) => (
              <HistoryListItem
                key={item.id}
                item={item}
                embedded={embedded}
                manageMode={manageMode}
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
              <div className="history-archive-state history-archive-state--compact">
                <div className="history-archive-state__pulse" />
                <p>{t('history.loadingMore')}</p>
              </div>
            )}

            {!hasMore && items.length > 0 && (
              <div className="history-archive-bottom">
                <span>{t('history.bottom')}</span>
              </div>
            )}
          </div>
        )}
      </ScrollArea>
    </aside>
  );
};
