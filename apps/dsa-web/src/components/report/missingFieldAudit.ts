import type { StandardReport, StandardReportField } from '../../types/analysis';

export type MissingFieldCategory =
  | 'integrated_unavailable'
  | 'not_integrated_yet'
  | 'source_not_provided'
  | 'not_applicable'
  | 'other_missing';

export interface MissingFieldEntry {
  field: string;
  reason: string;
  category: MissingFieldCategory;
  source: 'standard_report' | 'markdown';
  section?: string;
}

export interface MissingFieldAuditBucket {
  category: MissingFieldCategory;
  entries: MissingFieldEntry[];
}

export interface MissingFieldAuditSummary {
  totalMissingFields: number;
  buckets: MissingFieldAuditBucket[];
}

const MISSING_REASON_PATTERN = /(?:^|\b)NA\s*[（(]([^)）]+)[)）]/i;

const CATEGORY_ORDER: MissingFieldCategory[] = [
  'integrated_unavailable',
  'not_integrated_yet',
  'source_not_provided',
  'not_applicable',
  'other_missing',
];

const CATEGORY_PRIORITY: Record<MissingFieldCategory, number> = {
  not_integrated_yet: 0,
  source_not_provided: 1,
  integrated_unavailable: 2,
  not_applicable: 3,
  other_missing: 4,
};

const normalizeForKey = (value: string): string =>
  value
    .toLowerCase()
    .replace(/[\s.,，。!！?？:：;；、()（）【】'"“”‘’`]/g, '')
    .replace(/[[\]]/g, '')
    .trim();

const normalizeFieldLabel = (value: string): string =>
  value
    .replace(/[`*#>]/g, '')
    .replace(/\s+/g, ' ')
    .trim();

const NON_DATA_FIELD_LABEL_KEYS = new Set([
  '状态',
  '字段状态',
  'status',
  'fieldstatus',
  '冲突说明',
  '冲突备注',
  'conflictnote',
  'conflictnotes',
  'diagnostic',
  'diagnosticnote',
  'diagnosticnotes',
]);

const isAuditableFieldLabel = (value: string): boolean => {
  const normalized = normalizeForKey(value);
  if (!normalized) {
    return false;
  }
  return !NON_DATA_FIELD_LABEL_KEYS.has(normalized);
};

export const normalizeMissingFieldSemanticKey = (value: string): string => {
  const normalized = normalizeForKey(value);
  if (!normalized) {
    return '';
  }

  if (
    ['vwap', 'avgprice', 'averageprice', 'avgtradeprice', '均价', '平均价', '成交均价']
      .some((token) => normalized.includes(token))
  ) {
    return 'vwap';
  }

  return normalized;
};

const includesAny = (target: string, keywords: string[]): boolean =>
  keywords.some((keyword) => target.includes(keyword));

const parseMissingFieldNote = (value: string): { field: string; reason: string } | null => {
  const normalized = value.trim();
  if (!normalized) {
    return null;
  }

  const parts = normalized.split(/[：:]/);
  if (parts.length < 2) {
    return null;
  }

  const field = parts.shift()?.trim() || '';
  const reason = parts.join('：').trim();
  if (!field || !reason) {
    return null;
  }
  return { field, reason };
};

const pushMissingFieldEntries = (
  entries: MissingFieldEntry[],
  fields: StandardReportField[] | undefined,
  section: string,
) => {
  (fields || []).forEach((field) => {
    const normalizedField = normalizeFieldLabel(field.label || section);
    if (!isAuditableFieldLabel(normalizedField)) {
      return;
    }
    const reason = extractMissingReason(field.value);
    if (!reason) {
      return;
    }

    entries.push({
      field: normalizedField,
      reason,
      category: classifyMissingReason(reason),
      source: 'standard_report',
      section,
    });
  });
};

export const extractMissingReason = (value?: string | null): string | undefined => {
  const text = String(value || '').trim();
  if (!text) {
    return undefined;
  }
  const match = text.match(MISSING_REASON_PATTERN);
  if (!match) {
    return undefined;
  }
  return match[1]?.trim() || undefined;
};

export const classifyMissingReason = (reason: string): MissingFieldCategory => {
  const normalized = reason.trim().toLowerCase();

  if (
    includesAny(reason, ['不适用', '市场暂不支持', '会话不适用', '当前市场不支持'])
    || includesAny(normalized, ['not applicable', 'market not supported', 'session not applicable', 'unsupported market'])
  ) {
    return 'not_applicable';
  }

  if (
    includesAny(reason, ['字段待接入', '待接入', '未接入', '未集成', '待映射'])
    || includesAny(normalized, ['not integrated', 'integration pending', 'not mapped', 'pending mapping'])
  ) {
    return 'not_integrated_yet';
  }

  if (
    includesAny(reason, ['当前数据源未提供', '数据源未提供', '源未提供', '供应商未提供'])
    || includesAny(normalized, ['source not provided', 'provider does not provide', 'source limitation', 'provider limitation'])
  ) {
    return 'source_not_provided';
  }

  if (
    includesAny(reason, ['接口未返回', '未返回', '暂无数据', '样本不足', '暂不可用', '记录缺失'])
    || includesAny(normalized, ['not returned', 'no value returned', 'unavailable', 'no data', 'insufficient sample'])
  ) {
    return 'integrated_unavailable';
  }

  return 'other_missing';
};

export const collectMissingFieldEntriesFromStandardReport = (
  standardReport?: StandardReport,
): MissingFieldEntry[] => {
  if (!standardReport) {
    return [];
  }

  const entries: MissingFieldEntry[] = [];
  const sections: Array<[string, StandardReportField[] | undefined]> = [
    ['market_display', standardReport.market?.displayFields],
    ['market_regular', standardReport.market?.regularFields],
    ['market_extended', standardReport.market?.extendedFields],
    ['technical', standardReport.technicalFields],
    ['fundamental', standardReport.fundamentalFields],
    ['earnings', standardReport.earningsFields],
    ['sentiment', standardReport.sentimentFields],
    ['battle', standardReport.battleFields],
    ['table_market', standardReport.tableSections?.market?.fields],
    ['table_technical', standardReport.tableSections?.technical?.fields],
    ['table_fundamental', standardReport.tableSections?.fundamental?.fields],
    ['table_earnings', standardReport.tableSections?.earnings?.fields],
  ];

  sections.forEach(([section, fields]) => {
    pushMissingFieldEntries(entries, fields, section);
  });

  (standardReport.coverageNotes?.missingFieldNotes || []).forEach((note) => {
    const parsed = parseMissingFieldNote(note);
    if (!parsed) {
      return;
    }
    if (!isAuditableFieldLabel(parsed.field)) {
      return;
    }
    entries.push({
      field: normalizeFieldLabel(parsed.field),
      reason: parsed.reason,
      category: classifyMissingReason(parsed.reason),
      source: 'standard_report',
      section: 'coverage_notes',
    });
  });

  return dedupeMissingFieldEntries(entries);
};

export const collectMissingFieldEntriesFromMarkdown = (markdown: string): MissingFieldEntry[] => {
  const entries: MissingFieldEntry[] = [];
  const lines = markdown.split('\n');

  lines.forEach((line, index) => {
    const trimmed = line.trim();
    if (!trimmed || !MISSING_REASON_PATTERN.test(trimmed)) {
      return;
    }

    if (trimmed.startsWith('|')) {
      const cells = trimmed
        .split('|')
        .map((cell) => normalizeFieldLabel(cell))
        .filter(Boolean);

      cells.forEach((cell, cellIndex) => {
        const reason = extractMissingReason(cell);
        if (!reason) {
          return;
        }

        const field = normalizeFieldLabel(cells[Math.max(0, cellIndex - 1)] || `Markdown#${index + 1}`);
        if (!isAuditableFieldLabel(field) || extractMissingReason(field)) {
          return;
        }
        entries.push({
          field,
          reason,
          category: classifyMissingReason(reason),
          source: 'markdown',
          section: 'markdown_table',
        });
      });

      return;
    }

    const reason = extractMissingReason(trimmed);
    if (!reason) {
      return;
    }

    const colonLabelMatch = trimmed.match(
      /^(?:[-*+]\s*)?(?:\d+\.\s*)?(?:\*\*|__|`)?([^:：|]{1,100}?)(?:\*\*|__|`)?\s*[:：]\s*/,
    );

    const field = normalizeFieldLabel(colonLabelMatch?.[1] || `Markdown#${index + 1}`);
    if (!isAuditableFieldLabel(field) || extractMissingReason(field)) {
      return;
    }

    entries.push({
      field,
      reason,
      category: classifyMissingReason(reason),
      source: 'markdown',
      section: 'markdown_line',
    });
  });

  return dedupeMissingFieldEntries(entries);
};

export const dedupeMissingFieldEntries = (entries: MissingFieldEntry[]): MissingFieldEntry[] => {
  const deduped: MissingFieldEntry[] = [];
  const seen = new Set<string>();

  entries.forEach((entry) => {
    const key = [
      normalizeMissingFieldSemanticKey(entry.field) || normalizeForKey(entry.field),
      normalizeForKey(entry.reason),
      entry.category,
    ].join('|');
    if (seen.has(key)) {
      return;
    }
    seen.add(key);
    deduped.push(entry);
  });

  return deduped;
};

export const buildMissingFieldAudit = (entries: MissingFieldEntry[]): MissingFieldAuditSummary => {
  const dedupedEntries = dedupeMissingFieldEntries(entries);
  const groupedByField = new Map<string, MissingFieldEntry[]>();

  dedupedEntries.forEach((entry) => {
    const key = normalizeMissingFieldSemanticKey(entry.field);
    const current = groupedByField.get(key) || [];
    current.push(entry);
    groupedByField.set(key, current);
  });

  const consolidatedEntries: MissingFieldEntry[] = [];
  groupedByField.forEach((fieldEntries) => {
    const category = fieldEntries
      .map((entry) => entry.category)
      .sort((a, b) => CATEGORY_PRIORITY[a] - CATEGORY_PRIORITY[b])[0] || 'other_missing';
    const prioritized = fieldEntries.find((entry) => entry.category === category) || fieldEntries[0];

    consolidatedEntries.push({
      ...prioritized,
      category,
    });
  });

  const bucketMap = new Map<MissingFieldCategory, MissingFieldEntry[]>();

  CATEGORY_ORDER.forEach((category) => {
    bucketMap.set(category, []);
  });

  consolidatedEntries.forEach((entry) => {
    const current = bucketMap.get(entry.category);
    if (!current) {
      bucketMap.set(entry.category, [entry]);
      return;
    }
    current.push(entry);
  });

  return {
    totalMissingFields: consolidatedEntries.length,
    buckets: CATEGORY_ORDER.map((category) => ({
      category,
      entries: bucketMap.get(category) || [],
    })),
  };
};
