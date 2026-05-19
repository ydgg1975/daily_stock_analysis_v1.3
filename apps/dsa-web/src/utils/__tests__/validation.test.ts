import { describe, expect, test } from 'vitest';
import { isObviouslyInvalidStockQuery, looksLikeStockCode, validateStockCode } from '../validation';

describe('종목 검색어 검증', () => {
  test('한국 종목 코드 형식을 허용한다', () => {
    expect(looksLikeStockCode('KR005930')).toBe(true);
    expect(looksLikeStockCode('KS005930')).toBe(true);
    expect(looksLikeStockCode('KQ035720')).toBe(true);
    expect(looksLikeStockCode('005930.KS')).toBe(true);
    expect(looksLikeStockCode('035720.KQ')).toBe(true);
  });

  test('CN 접두어가 붙은 중국 종목 코드 형식을 허용한다', () => {
    expect(looksLikeStockCode('CN600519')).toBe(true);
    expect(looksLikeStockCode('600519.CN')).toBe(true);
  });

  test('한국 종목명을 잘못된 검색어로 거부하지 않는다', () => {
    expect(isObviouslyInvalidStockQuery('삼성전자')).toBe(false);
    expect(isObviouslyInvalidStockQuery('카카오')).toBe(false);
  });

  test('검증 메시지를 한국어로 반환한다', () => {
    expect(validateStockCode('').message).toBe('종목 코드를 입력하세요.');
    expect(validateStockCode('ABC123XYZ').message).toBe('종목 코드 형식이 올바르지 않습니다.');
  });
});
