import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Star } from 'lucide-react';
import { PageHeader, Badge, EmptyState, ConfirmDialog } from '../components/common';
import { AppPage } from '../components/common/AppPage';
import { StockAutocomplete } from '../components/StockAutocomplete/StockAutocomplete';
import { GroupSection } from '../components/watchlist/GroupSection';
import { watchlistApi, type WatchlistGroup } from '../api/watchlist';
import { scheduleApi, type ScheduleConfig } from '../api/schedule';

const WatchlistPage: React.FC = () => {
  const navigate = useNavigate();
  const [groups, setGroups] = useState<WatchlistGroup[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [addQuery, setAddQuery] = useState('');
  const [deleteGroupTarget, setDeleteGroupTarget] = useState<string | null>(null);
  const [schedule, setSchedule] = useState<ScheduleConfig | null>(null);

  // Flat list of group metadata for move-to submenu
  const groupMetas = useMemo(
    () => groups.map((g) => ({ groupId: g.groupId, groupName: g.groupName })),
    [groups],
  );

  // Total stock count across all groups
  const totalCount = useMemo(
    () => groups.reduce((sum, g) => sum + g.items.length, 0),
    [groups],
  );

  const fetchEnriched = useCallback(async () => {
    try {
      const data = await watchlistApi.getEnriched();
      setGroups(data.groups);
    } catch {
      // silently fail
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    document.title = '\u6211\u7684\u81EA\u9009 - DSA';
    void fetchEnriched();
    scheduleApi.get().then(setSchedule).catch(() => {
      // silently ignore
    });
  }, [fetchEnriched]);

  // --- Handlers ---

  const handleAnalyze = useCallback(
    (stockCode: string) => {
      navigate(`/?q=${encodeURIComponent(stockCode)}`);
    },
    [navigate],
  );

  const handleReanalyze = useCallback(
    (stockCode: string) => {
      navigate(`/?q=${encodeURIComponent(stockCode)}&force=1`);
    },
    [navigate],
  );

  const handleRemove = useCallback(
    async (stockCode: string) => {
      try {
        await watchlistApi.remove(stockCode);
        // Optimistic update
        setGroups((prev) =>
          prev.map((g) => ({
            ...g,
            items: g.items.filter((i) => i.stockCode !== stockCode),
          })),
        );
      } catch {
        // silently fail
      }
    },
    [],
  );

  const handleMoveGroup = useCallback(
    async (stockCode: string, targetGroupId: string) => {
      // Find the item and build new reorder payload
      let movedItem: WatchlistGroup['items'][number] | undefined;
      const updatedGroups = groups.map((g) => {
        const idx = g.items.findIndex((i) => i.stockCode === stockCode);
        if (idx >= 0) {
          movedItem = { ...g.items[idx], groupId: targetGroupId };
          return { ...g, items: [...g.items.slice(0, idx), ...g.items.slice(idx + 1)] };
        }
        return g;
      });

      if (!movedItem) return;

      const targetGroup = updatedGroups.find((g) => g.groupId === targetGroupId);
      if (targetGroup) {
        movedItem.sortOrder = targetGroup.items.length;
        targetGroup.items = [...targetGroup.items, movedItem];
      }

      setGroups(updatedGroups);

      // Build full reorder payload from the updated state
      const reorderItems = updatedGroups.flatMap((g) =>
        g.items.map((item, idx) => ({
          stockCode: item.stockCode,
          sortOrder: idx,
          groupId: g.groupId,
        })),
      );

      try {
        await watchlistApi.reorder(reorderItems);
      } catch {
        void fetchEnriched();
      }
    },
    [groups, fetchEnriched],
  );

  const handleMoveItem = useCallback(
    async (stockCode: string, direction: 'up' | 'down') => {
      const updatedGroups = groups.map((g) => {
        const idx = g.items.findIndex((i) => i.stockCode === stockCode);
        if (idx < 0) return g;

        const swapIdx = direction === 'up' ? idx - 1 : idx + 1;
        if (swapIdx < 0 || swapIdx >= g.items.length) return g;

        const newItems = [...g.items];
        [newItems[idx], newItems[swapIdx]] = [newItems[swapIdx], newItems[idx]];
        return { ...g, items: newItems };
      });

      setGroups(updatedGroups);

      const reorderItems = updatedGroups.flatMap((g) =>
        g.items.map((item, idx) => ({
          stockCode: item.stockCode,
          sortOrder: idx,
          groupId: g.groupId,
        })),
      );

      try {
        await watchlistApi.reorder(reorderItems);
      } catch {
        void fetchEnriched();
      }
    },
    [groups, fetchEnriched],
  );

  const handleAddStock = useCallback(
    async (stockCode?: string, stockName?: string) => {
      if (!stockCode) return;
      try {
        await watchlistApi.add(stockCode, stockName);
        setAddQuery('');
        void fetchEnriched();
      } catch {
        // silently fail
      }
    },
    [fetchEnriched],
  );

  const handleCreateGroup = useCallback(async () => {
    const name = window.prompt('\u65B0\u5206\u7EC4\u540D\u79F0');
    if (!name?.trim()) return;
    try {
      await watchlistApi.createGroup(name.trim());
      void fetchEnriched();
    } catch {
      // silently fail
    }
  }, [fetchEnriched]);

  const handleRenameGroup = useCallback(
    async (groupId: string, name: string) => {
      try {
        await watchlistApi.renameGroup(groupId, name);
        setGroups((prev) =>
          prev.map((g) => (g.groupId === groupId ? { ...g, groupName: name } : g)),
        );
      } catch {
        void fetchEnriched();
      }
    },
    [fetchEnriched],
  );

  const handleDeleteGroupConfirm = useCallback(async () => {
    if (!deleteGroupTarget) return;
    try {
      await watchlistApi.deleteGroup(deleteGroupTarget);
      void fetchEnriched();
    } catch {
      // silently fail
    } finally {
      setDeleteGroupTarget(null);
    }
  }, [deleteGroupTarget, fetchEnriched]);

  return (
    <AppPage>
      <PageHeader
        eyebrow="Watchlist"
        title={'\u6211\u7684\u81EA\u9009'}
        description={'\u6536\u85CF\u611F\u5174\u8DA3\u7684\u80A1\u7968\uFF0C\u5FEB\u901F\u67E5\u770B\u884C\u60C5\u4E0E\u5206\u6790'}
        actions={
          <div className="flex w-full flex-col gap-2 sm:w-auto sm:items-end">
            <div className="flex items-center gap-2">
              <div className="flex-1 sm:w-64 sm:flex-none">
                <StockAutocomplete
                  value={addQuery}
                  onChange={setAddQuery}
                  onSubmit={(code, name) => void handleAddStock(code, name)}
                  placeholder={'\u6DFB\u52A0\u80A1\u7968...'}
                />
              </div>
              <button
                type="button"
                onClick={handleCreateGroup}
                className="shrink-0 rounded-lg border border-subtle bg-surface/60 px-3 py-2 text-xs text-secondary-text transition-colors hover:border-subtle-hover hover:text-foreground"
              >
                + {'\u65B0\u5206\u7EC4'}
              </button>
            </div>
            {schedule !== null ? (
              schedule.enabled ? (
                <Badge variant="info">{'每日 ' + schedule.time + ' 自动分析'}</Badge>
              ) : (
                <span className="text-xs text-muted-text">
                  {'未开启定时 · '}
                  <Link to="/settings" className="text-cyan hover:underline">
                    开启
                  </Link>
                </span>
              )
            ) : null}
          </div>
        }
      />

      <div className="mt-6">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan/20 border-t-cyan" />
          </div>
        ) : totalCount === 0 ? (
          <EmptyState
            icon={<Star className="h-10 w-10 text-muted-text" />}
            title={'\u8FD8\u6CA1\u6709\u81EA\u9009\u80A1'}
            description={'\u5728\u4E0A\u65B9\u641C\u7D22\u6846\u6DFB\u52A0\u80A1\u7968\uFF0C\u6216\u5728\u9996\u9875\u70B9\u51FB \u2B50 \u6536\u85CF'}
          />
        ) : (
          groups.map((group) => (
            <GroupSection
              key={group.groupId}
              group={group}
              groups={groupMetas}
              onAnalyze={handleAnalyze}
              onReanalyze={handleReanalyze}
              onRemove={(code) => void handleRemove(code)}
              onMoveGroup={(code, gid) => void handleMoveGroup(code, gid)}
              onMoveItem={(code, dir) => void handleMoveItem(code, dir)}
              onRenameGroup={(gid, name) => void handleRenameGroup(gid, name)}
              onDeleteGroup={(gid) => setDeleteGroupTarget(gid)}
            />
          ))
        )}
      </div>

      <ConfirmDialog
        isOpen={deleteGroupTarget !== null}
        title={'\u5220\u9664\u5206\u7EC4'}
        message={'\u786E\u8BA4\u5220\u9664\u8FD9\u4E2A\u5206\u7EC4\u5417\uFF1F\u5206\u7EC4\u5185\u7684\u80A1\u7968\u5C06\u79FB\u56DE\u9ED8\u8BA4\u5206\u7EC4\u3002'}
        confirmText={'\u786E\u8BA4\u5220\u9664'}
        cancelText={'\u53D6\u6D88'}
        isDanger
        onConfirm={() => void handleDeleteGroupConfirm()}
        onCancel={() => setDeleteGroupTarget(null)}
      />
    </AppPage>
  );
};

export default WatchlistPage;
