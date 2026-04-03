import { describe, expect, it } from 'vitest';
import {
  buildMissingFieldAudit,
  classifyMissingReason,
  collectMissingFieldEntriesFromMarkdown,
  collectMissingFieldEntriesFromStandardReport,
} from '../missingFieldAudit';

describe('missingFieldAudit', () => {
  it('classifies missing reasons by integration/source/session causes', () => {
    expect(classifyMissingReason('接口未返回')).toBe('integrated_unavailable');
    expect(classifyMissingReason('字段待接入')).toBe('not_integrated_yet');
    expect(classifyMissingReason('当前数据源未提供')).toBe('source_not_provided');
    expect(classifyMissingReason('当前市场不支持')).toBe('not_applicable');
  });

  it('collects missing entries from standard report fields and coverage notes', () => {
    const entries = collectMissingFieldEntriesFromStandardReport({
      technicalFields: [
        { label: 'VWAP', value: 'NA（字段待接入）' },
        { label: 'RSI', value: '56.8' },
      ],
      coverageNotes: {
        missingFieldNotes: ['盘后成交量：当前数据源未提供'],
      },
    });

    expect(entries).toHaveLength(2);
    expect(entries.some((entry) => entry.field === 'VWAP' && entry.category === 'not_integrated_yet')).toBe(true);
    expect(entries.some((entry) => entry.field === '盘后成交量' && entry.category === 'source_not_provided')).toBe(true);
  });

  it('parses missing entries from markdown rows and keyed lines', () => {
    const entries = collectMissingFieldEntriesFromMarkdown(`
| 字段 | 值 |
| --- | --- |
| 盘前成交额 | NA（会话不适用） |
- 机构持仓: NA（接口未返回）
`);

    expect(entries).toHaveLength(2);
    expect(entries.some((entry) => entry.field === '盘前成交额' && entry.category === 'not_applicable')).toBe(true);
    expect(entries.some((entry) => entry.field === '机构持仓' && entry.category === 'integrated_unavailable')).toBe(true);
  });

  it('builds deduplicated bucket counts', () => {
    const entries = collectMissingFieldEntriesFromMarkdown('VWAP: NA（字段待接入）\nVWAP: NA（字段待接入）');
    const audit = buildMissingFieldAudit(entries);

    expect(audit.totalMissingFields).toBe(1);
    const notIntegratedBucket = audit.buckets.find((bucket) => bucket.category === 'not_integrated_yet');
    expect(notIntegratedBucket?.entries).toHaveLength(1);
  });

  it('normalizes equivalent field names into one audit entry with a single category', () => {
    const entries = collectMissingFieldEntriesFromMarkdown(`
VWAP: NA（字段待接入）
Avg Price: NA（当前数据源未提供）
均价: NA（接口未返回）
`);
    const audit = buildMissingFieldAudit(entries);

    expect(audit.totalMissingFields).toBe(1);
    const notIntegratedBucket = audit.buckets.find((bucket) => bucket.category === 'not_integrated_yet');
    expect(notIntegratedBucket?.entries).toHaveLength(1);
    expect(notIntegratedBucket?.entries[0]?.field).toBe('VWAP');
  });

  it('ignores diagnostic/meta labels in missing-field buckets', () => {
    const entries = collectMissingFieldEntriesFromMarkdown(`
状态: NA（接口未返回）
冲突说明: NA（接口未返回）
VWAP: NA（字段待接入）
`);
    const audit = buildMissingFieldAudit(entries);

    expect(audit.totalMissingFields).toBe(1);
    const onlyEntry = audit.buckets.flatMap((bucket) => bucket.entries);
    expect(onlyEntry).toHaveLength(1);
    expect(onlyEntry[0]?.field).toBe('VWAP');
  });
});
