import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useFuturesIndex } from '../useFuturesIndex';
import { stocksApi } from '../../api/stocks';

vi.mock('../../api/stocks', () => ({
  stocksApi: {
    getFuturesIndex: vi.fn(),
  },
}));

describe('useFuturesIndex', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads futures candidates from the backend index endpoint', async () => {
    vi.mocked(stocksApi.getFuturesIndex).mockResolvedValue([
      {
        canonicalCode: 'TA2609',
        displayCode: 'TA2609',
        nameZh: 'PTA2609',
        aliases: ['PTA', 'PTA2609'],
        market: 'FUTURES',
        assetType: 'futures',
        active: true,
        popularity: 100,
      },
    ]);

    const { result } = renderHook(() => useFuturesIndex());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.fallback).toBe(false);
    expect(result.current.index[0].canonicalCode).toBe('TA2609');
  });

  it('does not request the backend while disabled', () => {
    const { result } = renderHook(() => useFuturesIndex(false));

    expect(stocksApi.getFuturesIndex).not.toHaveBeenCalled();
    expect(result.current.loading).toBe(false);
    expect(result.current.index).toEqual([]);
  });
});
