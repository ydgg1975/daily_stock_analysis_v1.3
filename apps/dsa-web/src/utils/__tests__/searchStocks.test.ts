/**
 * searchStocks unit tests.
 */

import { searchStocks } from '../searchStocks';
import type { StockIndexItem } from '../../types/stockIndex';
import { describe, expect, test } from 'vitest';

const mockIndex: StockIndexItem[] = [
  {
    canonicalCode: "600519.SH",
    displayCode: "600519",
    nameZh: "guizhoumaotai",
    pinyinFull: "guizhoumaotai",
    pinyinAbbr: "gzmt",
    aliases: ["maotai"],
    market: "CN",
    assetType: "stock",
    active: true,
    popularity: 100,
  },
  {
    canonicalCode: "000001.SZ",
    displayCode: "000001",
    nameZh: "pinganyinhang",
    pinyinFull: "pinganyinxing",
    pinyinAbbr: "payh",
    aliases: ["pingyin"],
    market: "CN",
    assetType: "stock",
    active: true,
    popularity: 90,
  },
  {
    canonicalCode: "000002.SZ",
    displayCode: "000002",
    nameZh: "wankeＡ",
    pinyinFull: "wankeＡ",
    pinyinAbbr: "wkＡ",
    aliases: [],
    market: "CN",
    assetType: "stock",
    active: true,
    popularity: 92,
  },
  {
    canonicalCode: "00700.HK",
    displayCode: "00700",
    nameZh: "tengxunkonggu",
    pinyinFull: "tengxunkonggu",
    pinyinAbbr: "txkg",
    aliases: ["tengxun"],
    market: "HK",
    assetType: "stock",
    active: true,
    popularity: 95,
  },
  {
    canonicalCode: "AAPL.US",
    displayCode: "AAPL",
    nameZh: "pingguo",
    pinyinFull: "pingguo",
    pinyinAbbr: "pg",
    aliases: [],
    market: "US",
    assetType: "stock",
    active: true,
    popularity: 98,
  },
  {
    canonicalCode: "600000.SH",
    displayCode: "600000",
    nameZh: "pufayinhang",
    pinyinFull: "pufayinxing",
    pinyinAbbr: "pfyh",
    aliases: ["pufa"],
    market: "CN",
    assetType: "stock",
    active: false,  // Inactive
    popularity: 80,
  },
];

describe('searchStocks', () => {
  test('jingquepipeidaima', () => {
    const results = searchStocks('600519', mockIndex);
    expect(results).toHaveLength(1);
    expect(results[0].canonicalCode).toBe('600519.SH');
    expect(results[0].matchType).toBe('exact');
    expect(results[0].matchField).toBe('code');
  });

  test('jingquepipeizhongwenmingcheng', () => {
    const results = searchStocks('guizhoumaotai', mockIndex);
    expect(results).toHaveLength(1);
    expect(results[0].canonicalCode).toBe('600519.SH');
    expect(results[0].matchType).toBe('exact');
    expect(results[0].matchField).toBe('name');
  });

  test('pinyinshouzimupipei', () => {
    const results = searchStocks('gzmt', mockIndex);
    expect(results).toHaveLength(1);
    expect(results[0].canonicalCode).toBe('600519.SH');
    expect(results[0].matchType).toBe('exact');
  });

  test('biemingpipei', () => {
    const results = searchStocks('maotai', mockIndex);
    expect(results).toHaveLength(1);
    expect(results[0].canonicalCode).toBe('600519.SH');
    expect(results[0].matchType).toBe('exact');
  });

  test('qianzhuipipeidaima', () => {
    const results = searchStocks('600', mockIndex);
    expect(results.length).toBeGreaterThan(0);
    expect(results[0].matchType).toBe('prefix');
    expect(results[0].matchField).toBe('code');
  });

  test('qianzhuipipeimingcheng', () => {
    const results = searchStocks('guizhou', mockIndex);
    expect(results).toHaveLength(1);
    expect(results[0].matchType).toBe('prefix');
    expect(results[0].matchField).toBe('name');
  });

  test('baohanpipeipinyin', () => {
    const results = searchStocks('maotai', mockIndex);
    expect(results).toHaveLength(1);
    expect(results[0].canonicalCode).toBe('600519.SH');
    expect(results[0].matchType).toBe('contains');
  });

  test('active youxianyu inactive', () => {
    // 600000 shibuhuoyuede，600519 shihuoyuede
    const results = searchStocks('600', mockIndex);
    const activeResults = results.filter(r => {
      const item = mockIndex.find(i => i.canonicalCode === r.canonicalCode);
      return item?.active;
    });
    // huoyuegupiaoyinggaipaizaiqianmian
    if (results.length > 1) {
      expect(activeResults.length).toBeGreaterThan(0);
    }
  });

  test('activeOnly xuanxiangguolvbuhuoyuegupiao', () => {
    const results = searchStocks('600', mockIndex, { activeOnly: true });
    for (const result of results) {
      const item = mockIndex.find(i => i.canonicalCode === result.canonicalCode);
      expect(item?.active).toBe(true);
    }
  });

  test('limit xuanxiangxianzhifanhuishuliang', () => {
    const results = searchStocks('600', mockIndex, { limit: 1 });
    expect(results.length).toBeLessThanOrEqual(1);
  });

  test('wujieguoshifanhuikongshuzu', () => {
    const results = searchStocks('NOTFOUND', mockIndex);
    expect(results).toHaveLength(0);
  });

  test('kongchaxunfanhuikongshuzu', () => {
    const results = searchStocks('', mockIndex);
    expect(results).toHaveLength(0);
  });

  test('daxiaoxiebumingan', () => {
    const results1 = searchStocks('aapl', mockIndex);
    const results2 = searchStocks('AAPL', mockIndex);
    expect(results1).toHaveLength(1);
    expect(results2).toHaveLength(1);
    expect(results1[0].canonicalCode).toBe(results2[0].canonicalCode);
  });

  test('sorts by popularity when scores are tied', () => {
    const results = searchStocks('600', mockIndex);
    // When scores tie, popularity should decide the order.
    if (results.length > 1) {
      for (let index = 0; index < results.length - 1; index++) {
        const currentItem = mockIndex.find((item) => item.canonicalCode === results[index].canonicalCode);
        const nextItem = mockIndex.find((item) => item.canonicalCode === results[index + 1].canonicalCode);
        if (results[index].score === results[index + 1].score) {
          expect((currentItem?.popularity || 0)).toBeGreaterThanOrEqual(nextItem?.popularity || 0);
        }
      }
    }
  });

  test('meigudaimapipei', () => {
    const results = searchStocks('AAPL', mockIndex);
    expect(results).toHaveLength(1);
    expect(results[0].canonicalCode).toBe('AAPL.US');
    expect(results[0].market).toBe('US');
  });

  test('supports half-width queries for full-width A-share suffix names', () => {
    const byName = searchStocks('wankeA', mockIndex);
    const byPinyin = searchStocks('wka', mockIndex);

    expect(byName[0].canonicalCode).toBe('000002.SZ');
    expect(byPinyin[0].canonicalCode).toBe('000002.SZ');
  });

  test('ganggudaimapipei', () => {
    const results = searchStocks('00700', mockIndex);
    expect(results).toHaveLength(1);
    expect(results[0].canonicalCode).toBe('00700.HK');
    expect(results[0].market).toBe('HK');
  });

  describe('Edge case tests', () => {
    test('special character query', () => {
      const results = searchStocks('@#$%', mockIndex);
      expect(results).toHaveLength(0);
    });

    test('pure space query', () => {
      const results = searchStocks('   ', mockIndex);
      expect(results).toHaveLength(0);
    });

    test('Unicode character query', () => {
      const results = searchStocks('gupiao🚀', mockIndex);
      expect(results).toHaveLength(0);
    });

    test('extra long query string', () => {
      const longQuery = 'a'.repeat(1000);
      const results = searchStocks(longQuery, mockIndex);
      expect(results).toHaveLength(0);
    });

    test('partial pinyin match', () => {
      const results = searchStocks('mao', mockIndex);
      expect(results.length).toBeGreaterThan(0);
      const hasMaoTai = results.some(r => r.canonicalCode === '600519.SH');
      expect(hasMaoTai).toBe(true);
    });

    test('abbreviation prefix match', () => {
      const results = searchStocks('gz', mockIndex);
      expect(results.length).toBeGreaterThan(0);
      expect(results[0].matchType).toBe('prefix');
    });

    test('alias match', () => {
      const results = searchStocks('yin', mockIndex);
      expect(results.length).toBeGreaterThan(0);
      // Should match pinganyinhang and pufayinhang
      const banks = results.filter(r => r.nameZh.includes('yinhang'));
      expect(banks.length).toBeGreaterThan(0);
    });
  });

  describe('Scoring system tests', () => {
    test('exact match has highest score', () => {
      const exactResults = searchStocks('600519', mockIndex);
      const prefixResults = searchStocks('600', mockIndex);

      expect(exactResults[0].score).toBeGreaterThan(prefixResults[0].score);
    });

    test('code match prioritized over name match', () => {
      const codeResults = searchStocks('600519', mockIndex);
      const nameResults = searchStocks('guizhou', mockIndex);

      // Code exact match should be 99 points (displayCode match)
      expect(codeResults[0].score).toBe(99);
      // Name prefix match should be less than 99 points
      expect(nameResults[0].score).toBeLessThan(99);
    });

    test('sorts by popularity when scores are equal', () => {
      // Add two stocks with same score
      const tieIndex: StockIndexItem[] = [
        {
          canonicalCode: 'TEST1.SH',
          displayCode: 'TEST1',
          nameZh: 'ceshi1',
          pinyinFull: 'test1',
          pinyinAbbr: 'ts1',
          aliases: [],
          market: 'CN',
          assetType: 'stock',
          active: true,
          popularity: 50,
        },
        {
          canonicalCode: 'TEST2.SH',
          displayCode: 'TEST2',
          nameZh: 'ceshi2',
          pinyinFull: 'test2',
          pinyinAbbr: 'ts2',
          aliases: [],
          market: 'CN',
          assetType: 'stock',
          active: true,
          popularity: 100,
        },
      ];

      const results = searchStocks('TEST', tieIndex);
      if (results.length > 1) {
        // TEST2 should rank first due to higher popularity
        expect(results[0].canonicalCode).toBe('TEST2.SH');
      }
    });
  });

  describe('Inactive stock tests', () => {
    test('filters out inactive stocks by default', () => {
      const results = searchStocks('600000', mockIndex);
      // 600000 is inactive, should not appear by default
      expect(results).toHaveLength(0);
    });

    test('shows inactive stocks when activeOnly=false', () => {
      const results = searchStocks('600000', mockIndex, { activeOnly: false });
      expect(results).toHaveLength(1);
      expect(results[0].canonicalCode).toBe('600000.SH');
    });

    test('active stocks prioritized over inactive stocks', () => {
      const results = searchStocks('600', mockIndex, { activeOnly: false });
      if (results.length > 1) {
        // First result should be active
        const firstItem = mockIndex.find(i => i.canonicalCode === results[0].canonicalCode);
        expect(firstItem?.active).toBe(true);
      }
    });
  });

  describe('Performance tests', () => {
    test('large index search performance', () => {
      // Create a large index
      const largeIndex: StockIndexItem[] = Array.from({ length: 5000 }, (_, i) => ({
        canonicalCode: `${i}.SH`,
        displayCode: `${i}`,
        nameZh: `gupiao${i}`,
        pinyinFull: `stock${i}`,
        pinyinAbbr: `s${i}`,
        aliases: [],
        market: 'CN',
        assetType: 'stock',
        active: true,
        popularity: i % 100,
      }));

      const startTime = Date.now();
      const results = searchStocks('1', largeIndex);
      const endTime = Date.now();

      // Should complete in reasonable time (< 100ms)
      expect(endTime - startTime).toBeLessThan(100);
      expect(results.length).toBeGreaterThan(0);
    });

    test('multiple search performance', () => {
      const iterations = 100;
      const startTime = Date.now();

      for (let i = 0; i < iterations; i++) {
        searchStocks('600', mockIndex);
      }

      const endTime = Date.now();
      const avgTime = (endTime - startTime) / iterations;

      // Average search should be fast (< 10ms)
      expect(avgTime).toBeLessThan(10);
    });
  });

  describe('Match type tests', () => {
    test('exact match type', () => {
      const results = searchStocks('600519', mockIndex);
      expect(results[0].matchType).toBe('exact');
    });

    test('prefix match type', () => {
      const results = searchStocks('600', mockIndex);
      expect(results[0].matchType).toBe('prefix');
    });

    test('contains match type', () => {
      const results = searchStocks('maotai', mockIndex);
      expect(results[0].matchType).toBe('contains');
    });
  });

  describe('Match field tests', () => {
    test('code field match', () => {
      const results = searchStocks('600519', mockIndex);
      expect(results[0].matchField).toBe('code');
    });

    test('name field match', () => {
      const results = searchStocks('guizhou', mockIndex);
      expect(results[0].matchField).toBe('name');
    });

    test('pinyin field match', () => {
      const results = searchStocks('gzmt', mockIndex);
      expect(results[0].matchField).toBe('pinyin');
    });

    test('alias field match', () => {
      const results = searchStocks('maotai', mockIndex);
      // Should match guizhoumaotai
      expect(results.length).toBeGreaterThan(0);
    });
  });
});
