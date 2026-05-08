import { useEffect, useState } from 'react';
import { stocksApi } from '../api/stocks';
import type { StockIndexItem } from '../types/stockIndex';
import { buildFuturesIndex } from '../utils/futuresIndex';

export interface UseFuturesIndexResult {
  index: StockIndexItem[];
  loading: boolean;
  error: Error | null;
  fallback: boolean;
  loaded: boolean;
}

export function useFuturesIndex(enabled = true): UseFuturesIndexResult {
  const [index, setIndex] = useState<StockIndexItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [fallback, setFallback] = useState(false);

  useEffect(() => {
    let mounted = true;

    if (!enabled) {
      setIndex([]);
      setLoading(false);
      setError(null);
      setFallback(false);
      return () => {
        mounted = false;
      };
    }

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const items = await stocksApi.getFuturesIndex();
        if (!mounted) {
          return;
        }
        if (items.length > 0) {
          setIndex(items);
          setFallback(false);
        } else {
          setIndex(buildFuturesIndex());
          setFallback(true);
        }
      } catch (caught) {
        if (!mounted) {
          return;
        }
        const runtimeError = caught instanceof Error ? caught : new Error('Failed to load futures index');
        console.error('[FuturesIndexLoader] Failed to load futures index:', runtimeError);
        setIndex(buildFuturesIndex());
        setError(runtimeError);
        setFallback(true);
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    load();

    return () => {
      mounted = false;
    };
  }, [enabled]);

  return {
    index,
    loading,
    error,
    fallback,
    loaded: !loading,
  };
}

export default useFuturesIndex;
