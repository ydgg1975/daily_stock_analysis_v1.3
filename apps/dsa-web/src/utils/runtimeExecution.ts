import type {
  AnalysisReport,
  RuntimeExecutionField,
  RuntimeExecutionSummary,
  TaskInfo,
} from '../types/analysis';
import { inferAnalysisStage } from './analysisStatus';

type AnyRecord = Record<string, unknown>;

const SUCCESS_STATUSES = new Set(['ok', 'success', 'partial']);
const KNOWN_RUNTIME_STATUSES = new Set([
  'ok',
  'success',
  'partial',
  'failed',
  'attempting',
  'waiting',
  'unknown',
  'unavailable',
  'skipped',
  'not_configured',
  'configured_not_used',
  'used_unrecorded',
]);

function asRecord(value: unknown): AnyRecord | null {
  return value && typeof value === 'object' ? value as AnyRecord : null;
}

function asString(value: unknown): string | null {
  if (value === null || value === undefined) {
    return null;
  }
  const text = String(value).trim();
  return text ? text : null;
}

function normalizeTruth(value: unknown): 'actual' | 'inferred' | 'unavailable' {
  const raw = String(value || '').trim().toLowerCase();
  if (raw === 'actual' || raw === 'inferred' || raw === 'unavailable') {
    return raw;
  }
  return 'unavailable';
}

function normalizeStatus(value: unknown, fallback = 'unknown'): string {
  const normalized = String(value || '').trim().toLowerCase();
  if (KNOWN_RUNTIME_STATUSES.has(normalized)) {
    return normalized;
  }
  return fallback;
}

function withRunningStatus(
  field: (RuntimeExecutionField & { sourceChain?: Array<Record<string, unknown>> }) | undefined,
  task: TaskInfo,
): (RuntimeExecutionField & { sourceChain?: Array<Record<string, unknown>> }) | undefined {
  if (!field || task.status !== 'processing') {
    return field;
  }
  const currentStatus = normalizeStatus((field as Record<string, unknown>).status);
  const source = asString((field as Record<string, unknown>).source);
  if (!source) {
    return field;
  }
  if (currentStatus !== 'unknown' && currentStatus !== 'unavailable') {
    return field;
  }
  return {
    ...(field as Record<string, unknown>),
    status: 'attempting',
  } as typeof field;
}

function parseProviderFromModel(model: string | null): string | null {
  if (!model || !model.includes('/')) {
    return null;
  }
  const provider = model.split('/', 1)[0]?.trim();
  return provider || null;
}

function pickSourceFromChain(chain: unknown): { source: string | null; fallback: boolean } {
  if (!Array.isArray(chain)) {
    return { source: null, fallback: false };
  }
  const normalized = chain
    .map((item) => asRecord(item))
    .filter((item): item is AnyRecord => Boolean(item));
  if (!normalized.length) {
    return { source: null, fallback: false };
  }

  const successIndex = normalized.findIndex((item) => {
    const status = String(item.result || '').trim().toLowerCase();
    return SUCCESS_STATUSES.has(status);
  });
  if (successIndex >= 0) {
    return {
      source: asString(normalized[successIndex].provider),
      fallback: successIndex > 0,
    };
  }
  return {
    source: asString(normalized[0].provider),
    fallback: normalized.length > 1,
  };
}

function inferTaskSteps(task: TaskInfo): RuntimeExecutionSummary['steps'] {
  const stage = inferAnalysisStage(task, { isSubmitting: false }) || 'queued';
  const statusByStep: Record<string, string> = {
    data_fetch: 'unknown',
    ai_analysis: 'unknown',
    notification: 'unknown',
  };

  if (stage === 'fetching') {
    statusByStep.data_fetch = 'partial';
  } else if (stage === 'generating') {
    statusByStep.data_fetch = 'ok';
    statusByStep.ai_analysis = 'partial';
  } else if (stage === 'notifying') {
    statusByStep.data_fetch = 'ok';
    statusByStep.ai_analysis = 'ok';
    statusByStep.notification = 'partial';
  } else if (stage === 'completed') {
    statusByStep.data_fetch = 'ok';
    statusByStep.ai_analysis = 'ok';
    statusByStep.notification = 'ok';
  } else if (stage === 'failed') {
    statusByStep.ai_analysis = 'failed';
  }

  return [
    { key: 'data_fetch', status: statusByStep.data_fetch },
    { key: 'ai_analysis', status: statusByStep.ai_analysis },
    { key: 'notification', status: statusByStep.notification },
  ];
}

function mergeNotification(
  runtimeExecution: RuntimeExecutionSummary | null,
  rawResult: AnyRecord | null,
): RuntimeExecutionSummary | null {
  if (!runtimeExecution) {
    return runtimeExecution;
  }

  const rawNotification = asRecord(rawResult?.notificationResult);
  if (!rawNotification || runtimeExecution.notification) {
    return runtimeExecution;
  }

  return {
    ...runtimeExecution,
    notification: {
      attempted: Boolean(rawNotification.attempted),
      status: asString(rawNotification.status) || 'unknown',
      success: typeof rawNotification.success === 'boolean' ? rawNotification.success : null,
      channels: Array.isArray(rawNotification.channels)
        ? rawNotification.channels.map((item) => String(item))
        : [],
      truth: normalizeTruth(rawNotification.truth || 'actual'),
      error: asString(rawNotification.error) || undefined,
    },
  };
}

export function buildTaskExecutionSummary(task: TaskInfo): RuntimeExecutionSummary | null {
  if (task.execution) {
    const runtime = task.execution;
    if (task.status !== 'processing' && task.status !== 'pending') {
      return runtime;
    }

    const liveSteps = inferTaskSteps(task) || [];
    const runtimeSteps = Array.isArray(runtime.steps) ? runtime.steps : [];
    const mergedStepMap = new Map<string, { key: string; status: string; detail?: string }>();

    runtimeSteps.forEach((step) => {
      const key = String(step?.key || '').trim();
      if (!key) return;
      mergedStepMap.set(key, {
        key,
        status: normalizeStatus(step?.status),
        detail: step?.detail,
      });
    });
    liveSteps.forEach((step) => {
      const key = String(step?.key || '').trim();
      if (!key) return;
      const existing = mergedStepMap.get(key);
      if (!existing || ['unknown', 'unavailable', 'waiting'].includes(existing.status)) {
        mergedStepMap.set(key, { ...existing, key, status: normalizeStatus(step.status) });
      }
    });

    return {
      ...runtime,
      data: {
        market: withRunningStatus(runtime.data?.market, task),
        fundamentals: withRunningStatus(runtime.data?.fundamentals, task),
        news: withRunningStatus(runtime.data?.news, task),
        sentiment: withRunningStatus(runtime.data?.sentiment, task),
      },
      steps: [...mergedStepMap.values()],
    };
  }

  // No runtime payload from backend yet. Keep transparent and avoid pretending certainty.
  return {
    ai: {
      model: null,
      provider: null,
      gateway: null,
      modelTruth: 'unavailable',
      providerTruth: 'unavailable',
      gatewayTruth: 'unavailable',
      fallbackOccurred: false,
      fallbackTruth: 'unavailable',
      configuredPrimaryModel: null,
    },
    data: {
      market: { source: null, truth: 'inferred', fallbackOccurred: false, status: 'unknown' },
      fundamentals: { source: null, truth: 'inferred', fallbackOccurred: false, status: 'unknown' },
      news: { source: null, truth: 'inferred', fallbackOccurred: false, status: 'used_unrecorded' },
      sentiment: { source: null, truth: 'inferred', fallbackOccurred: false, status: 'used_unrecorded' },
    },
    notification: {
      attempted: false,
      status: task.status === 'processing' ? 'unknown' : 'unavailable',
      success: null,
      channels: [],
      truth: 'unavailable',
    },
    steps: inferTaskSteps(task),
  };
}

export function buildReportExecutionSummary(report: AnalysisReport): RuntimeExecutionSummary | null {
  const rawResult = asRecord(report.details?.rawResult);
  const rawRuntime = asRecord(rawResult?.runtimeExecution);
  const normalizedRawRuntime = rawRuntime as RuntimeExecutionSummary | null;
  if (normalizedRawRuntime) {
    return mergeNotification(normalizedRawRuntime, rawResult);
  }

  const contextSnapshot = asRecord(report.details?.contextSnapshot);
  const enhancedContext = asRecord(contextSnapshot?.enhancedContext);
  const realtime = asRecord(enhancedContext?.realtime);
  const fundamentalContext = asRecord(enhancedContext?.fundamentalContext);
  const sentimentAnalysis = asRecord(enhancedContext?.sentimentAnalysis);
  const dataQuality = asRecord(enhancedContext?.dataQuality);
  const providerNotes = asRecord(dataQuality?.providerNotes);

  const modelUsed = asString(report.meta.modelUsed) || asString(rawResult?.modelUsed);
  const provider = parseProviderFromModel(modelUsed);

  const marketSource = asString(realtime?.source);
  const fundamentalSourceInfo = pickSourceFromChain(fundamentalContext?.sourceChain);
  const searchEnabled = Boolean(
    asString(providerNotes?.sentiment)
    || Array.isArray(asRecord(sentimentAnalysis)?.classifiedItems)
    || asString(sentimentAnalysis?.status),
  );
  const rawNews = asRecord(asRecord(rawRuntime?.data)?.news);
  const rawSentiment = asRecord(asRecord(rawRuntime?.data)?.sentiment);
  const newsSource = asString(rawNews?.source)
    || asString(providerNotes?.news)
    || asString(providerNotes?.sentiment);
  const sentimentSource = asString(rawSentiment?.source) || asString(providerNotes?.sentiment);
  const sentimentStatus = normalizeStatus(asString(rawSentiment?.status) || asString(sentimentAnalysis?.status));
  const newsStatus = normalizeStatus(asString(rawNews?.status), searchEnabled ? 'configured_not_used' : sentimentStatus);
  const newsTruth = newsSource ? 'actual' : (searchEnabled ? 'inferred' : 'unavailable');
  const sentimentTruth = sentimentSource ? 'actual' : (searchEnabled ? 'inferred' : 'unavailable');

  return {
    ai: {
      model: modelUsed,
      provider,
      gateway: null,
      modelTruth: modelUsed ? 'actual' : 'unavailable',
      providerTruth: provider ? 'inferred' : 'unavailable',
      gatewayTruth: 'unavailable',
      fallbackOccurred: false,
      fallbackTruth: 'unavailable',
      configuredPrimaryModel: null,
    },
    data: {
      market: {
        source: marketSource,
        truth: marketSource ? 'actual' : 'unavailable',
        fallbackOccurred: Boolean(marketSource && marketSource.toLowerCase().includes('fallback')),
        status: marketSource ? 'ok' : 'unknown',
      },
      fundamentals: {
        source: fundamentalSourceInfo.source,
        truth: fundamentalSourceInfo.source ? 'actual' : 'unavailable',
        fallbackOccurred: fundamentalSourceInfo.fallback,
        status: asString(fundamentalContext?.status) || 'unknown',
        sourceChain: Array.isArray(fundamentalContext?.sourceChain)
          ? (fundamentalContext?.sourceChain as Array<Record<string, unknown>>)
          : [],
      },
      news: {
        source: newsSource,
        truth: newsTruth,
        fallbackOccurred: Boolean(asRecord(rawNews)?.fallbackOccurred),
        status: newsStatus,
      },
      sentiment: {
        source: sentimentSource,
        truth: sentimentTruth,
        fallbackOccurred: false,
        status: sentimentStatus,
      },
    },
    notification: {
      attempted: false,
      status: 'unavailable',
      success: null,
      channels: [],
      truth: 'unavailable',
    },
    steps: [
      { key: 'data_fetch', status: marketSource ? 'ok' : 'unknown' },
      { key: 'ai_analysis', status: modelUsed ? 'ok' : 'unknown' },
      { key: 'notification', status: 'unavailable' },
    ],
  };
}

export function truthToKey(truth: unknown): 'actual' | 'inferred' | 'unavailable' {
  return normalizeTruth(truth);
}
