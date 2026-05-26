import { describe, expect, test } from 'vitest';
import { isObviouslyInvalidStockQuery, looksLikeStockCode, validateStockCode } from '../validation';

describe('종목 검색어 검증', () => {
  test('한국 종목 코드 형식을 허용한다', () => {
    expect(looksLikeStockCode('005930')).toBe(true);
    expect(looksLikeStockCode('KR005930')).toBe(true);
    expect(looksLikeStockCode('KS005930')).toBe(true);
    expect(looksLikeStockCode('KQ091990')).toBe(true);
    expect(looksLikeStockCode('005930.KS')).toBe(true);
    expect(looksLikeStockCode('091990.KQ')).toBe(true);
  });

  test('중국/HK 종목 코드 형식은 기본 분석 입력에서 제외한다', () => {
    expect(looksLikeStockCode('CN600519')).toBe(false);
    expect(looksLikeStockCode('600519.CN')).toBe(false);
    expect(looksLikeStockCode('HK00700')).toBe(false);
    expect(looksLikeStockCode('00700.HK')).toBe(false);
  });

  test('한국 종목명을 잘못된 검색어로 거부하지 않는다', () => {
    expect(isObviouslyInvalidStockQuery('삼성전자')).toBe(false);
    expect(isObviouslyInvalidStockQuery('카카오')).toBe(false);
  });

  test('검증 메시지를 한국어로 반환한다', () => {
    expect(validateStockCode('').message).toBe('종목 코드나 이름을 입력하세요.');
    expect(validateStockCode('ABC123XYZ').message).toBe(
      '지원하는 종목 형식이 아닙니다. 예: 005930.KS, 091990.KQ, AAPL',
    );
  });
});
