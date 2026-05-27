import { describe, expect, it } from 'vitest';
import { getFieldDescriptionZh, getFieldTitleZh } from '../src/utils/systemConfigI18n';

const requiredLocalizedKeys = [
  'STOCK_LIST',
  'NEWS_STRATEGY_PROFILE',
  'LITELLM_MODEL',
  'OPENAI_API_KEY',
  'CUSTOM_WEBHOOK_BODY_TEMPLATE',
  'REPORT_TYPE',
  'REPORT_LANGUAGE',
  'MARKET_REVIEW_COLOR_SCHEME',
  'LOG_LEVEL',
] as const;

describe('systemConfigI18n required key coverage', () => {
  it('provides localized title and description mapping for known keys', () => {
    requiredLocalizedKeys.forEach((key) => {
      expect(getFieldTitleZh(key, key)).not.toBe(key);
      expect(getFieldDescriptionZh(key, 'schema fallback description')).toBeTruthy();
    });
  });
});
