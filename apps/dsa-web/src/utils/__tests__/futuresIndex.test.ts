import { describe, expect, it } from 'vitest';
import { buildFuturesIndex } from '../futuresIndex';
import { searchStocks } from '../searchStocks';

describe('futuresIndex', () => {
  it('matches a Chinese futures contract query to its exchange code', () => {
    const index = buildFuturesIndex(new Date('2026-05-07T00:00:00+08:00'));

    const suggestions = searchStocks('焦煤2609', index);

    expect(suggestions[0]).toMatchObject({
      canonicalCode: 'JM2609',
      displayCode: 'JM2609',
      nameZh: '焦煤2609',
      market: 'FUTURES',
    });
  });
});
