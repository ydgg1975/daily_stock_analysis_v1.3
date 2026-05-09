import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Button, InlineAlert } from '../common';
import { SystemConfigConflictError, systemConfigApi } from '../../api/systemConfig';
import { getParsedApiError } from '../../api/error';
import { cn } from '../../utils/cn';
import { validateStockCode } from '../../utils/validation';

type WatchlistQuickActionProps = {
  stockCode?: string | null;
  stockName?: string | null;
  buttonVariant?: 'action-primary' | 'action-secondary' | 'home-action-ai' | 'home-action-report';
  size?: 'xsm' | 'sm' | 'md';
  className?: string;
};

type FeedbackState =
  | { type: 'success'; message: string }
  | { type: 'error'; message: string }
  | null;

function normalizeWatchlistCode(stockCode: string): string {
  const { valid, normalized } = validateStockCode(stockCode);
  return valid ? normalized : stockCode.trim().toUpperCase();
}

function parseStockList(rawValue: string): string[] {
  const seen = new Set<string>();
  const values: string[] = [];

  for (const entry of rawValue.split(',')) {
    const normalized = normalizeWatchlistCode(entry);
    if (!normalized || seen.has(normalized)) {
      continue;
    }
    seen.add(normalized);
    values.push(normalized);
  }

  return values;
}

async function updateWatchlistMembership(
  targetCode: string,
  shouldAdd: boolean,
): Promise<boolean> {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const config = await systemConfigApi.getConfig(false);
    const currentItem = config.items.find((item) => item.key === 'STOCK_LIST');
    const currentList = parseStockList(currentItem?.value ?? '');
    const hasTarget = currentList.includes(targetCode);
    const nextList = shouldAdd
      ? (hasTarget ? currentList : [...currentList, targetCode])
      : currentList.filter((code) => code !== targetCode);

    if (hasTarget === shouldAdd) {
      return hasTarget;
    }

    try {
      await systemConfigApi.update({
        configVersion: config.configVersion,
        maskToken: config.maskToken,
        items: [{ key: 'STOCK_LIST', value: nextList.join(',') }],
      });
      return shouldAdd;
    } catch (error) {
      if (error instanceof SystemConfigConflictError && attempt === 0) {
        continue;
      }
      throw error;
    }
  }

  return shouldAdd;
}

export const WatchlistQuickAction: React.FC<WatchlistQuickActionProps> = ({
  stockCode,
  stockName,
  buttonVariant = 'home-action-ai',
  size = 'sm',
  className,
}) => {
  const normalizedStockCode = useMemo(() => {
    const raw = (stockCode || '').trim();
    if (!raw) {
      return '';
    }
    const { valid, normalized } = validateStockCode(raw);
    return valid ? normalized : '';
  }, [stockCode]);
  const displayName = stockName?.trim() || normalizedStockCode;

  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isWatched, setIsWatched] = useState(false);
  const [feedback, setFeedback] = useState<FeedbackState>(null);

  const loadWatchlistStatus = useCallback(async () => {
    if (!normalizedStockCode) {
      setIsWatched(false);
      return;
    }

    setIsLoading(true);
    try {
      const config = await systemConfigApi.getConfig(false);
      const currentItem = config.items.find((item) => item.key === 'STOCK_LIST');
      const currentList = parseStockList(currentItem?.value ?? '');
      setIsWatched(currentList.includes(normalizedStockCode));
    } catch {
      setIsWatched(false);
    } finally {
      setIsLoading(false);
    }
  }, [normalizedStockCode]);

  useEffect(() => {
    setFeedback(null);
    void loadWatchlistStatus();
  }, [loadWatchlistStatus]);

  const handleToggleWatchlist = useCallback(async () => {
    if (!normalizedStockCode || isSaving) {
      return;
    }

    const shouldAdd = !isWatched;
    setIsSaving(true);
    setFeedback(null);

    try {
      const nextWatched = await updateWatchlistMembership(normalizedStockCode, shouldAdd);
      setIsWatched(nextWatched);
      setFeedback({
        type: 'success',
        message: nextWatched
          ? `${displayName} 已加入观察队列`
          : `${displayName} 已移出观察队列`,
      });
    } catch (error) {
      const parsed = getParsedApiError(error);
      setFeedback({
        type: 'error',
        message: parsed.message || '更新观察队列失败',
      });
    } finally {
      setIsSaving(false);
    }
  }, [displayName, isSaving, isWatched, normalizedStockCode]);

  if (!normalizedStockCode) {
    return null;
  }

  return (
    <div className={cn('flex flex-col gap-2', className)}>
      <Button
        variant={buttonVariant}
        size={size}
        disabled={isLoading || isSaving}
        isLoading={isSaving}
        loadingText={isWatched ? '移出中...' : '加入中...'}
        onClick={() => void handleToggleWatchlist()}
        aria-label={isWatched ? '取消观察队列' : '加入观察队列'}
      >
        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d={isWatched ? 'M5 13l4 4L19 7' : 'M12 4v16m8-8H4'}
          />
        </svg>
        {isWatched ? '取消观察队列' : '加入观察队列'}
      </Button>
      {feedback ? (
        <InlineAlert
          variant={feedback.type === 'success' ? 'success' : 'danger'}
          title={feedback.type === 'success' ? '观察队列已更新' : '观察队列更新失败'}
          message={feedback.message}
          className="rounded-xl px-3 py-2 text-xs shadow-none"
        />
      ) : null}
    </div>
  );
};

export default WatchlistQuickAction;
