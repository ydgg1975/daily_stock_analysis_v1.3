import type React from 'react';
import type { RuntimeExecutionSummary } from '../../types/analysis';
import { useI18n } from '../../contexts/UiLanguageContext';
import { truthToKey } from '../../utils/runtimeExecution';

interface ExecutionSummaryCardProps {
  summary: RuntimeExecutionSummary | null;
  compact?: boolean;
}

const TRUTH_TONE_CLASS: Record<string, string> = {
  actual: 'text-[hsl(var(--accent-positive-hsl))]',
  inferred: 'text-[hsl(var(--accent-warning-hsl))]',
  unavailable: 'text-muted-text',
};

const STATUS_TONE_CLASS: Record<string, string> = {
  ok: 'text-[hsl(var(--accent-positive-hsl))]',
  success: 'text-[hsl(var(--accent-positive-hsl))]',
  partial: 'text-[hsl(var(--accent-warning-hsl))]',
  failed: 'text-[hsl(var(--accent-danger-hsl))]',
  attempting: 'text-[hsl(var(--accent-warning-hsl))]',
  waiting: 'text-muted-text',
  unknown: 'text-muted-text',
  unavailable: 'text-muted-text',
  skipped: 'text-muted-text',
  not_configured: 'text-muted-text',
  configured_not_used: 'text-[hsl(var(--accent-warning-hsl))]',
  used_unrecorded: 'text-[hsl(var(--accent-warning-hsl))]',
};

function formatValue(value: unknown, fallback: string): string {
  const text = String(value || '').trim();
  return text || fallback;
}

export const ExecutionSummaryCard: React.FC<ExecutionSummaryCardProps> = ({ summary, compact = false }) => {
  const { t } = useI18n();
  const fallbackText = t('runtime.unknown');
  const unavailableText = t('runtime.unavailable');

  const aiModel = formatValue(summary?.ai?.model, unavailableText);
  const aiProvider = formatValue(summary?.ai?.provider, unavailableText);
  const aiGateway = formatValue(summary?.ai?.gateway, unavailableText);
  const marketSource = formatValue(summary?.data?.market?.source, unavailableText);
  const fundamentalSource = formatValue(summary?.data?.fundamentals?.source, unavailableText);
  const newsSource = formatValue(summary?.data?.news?.source, unavailableText);
  const sentimentSource = formatValue(summary?.data?.sentiment?.source, unavailableText);
  const newsStatus = String(summary?.data?.news?.status || 'unknown').toLowerCase();
  const sentimentStatus = String(summary?.data?.sentiment?.status || 'unknown').toLowerCase();
  const newsTruth = truthToKey(summary?.data?.news?.truth);
  const sentimentTruth = truthToKey(summary?.data?.sentiment?.truth);

  const notificationStatus = String(summary?.notification?.status || 'unavailable').toLowerCase();
  const notificationChannels = (summary?.notification?.channels || []).join(', ') || unavailableText;

  const aiTruth = truthToKey(summary?.ai?.modelTruth);
  const marketTruth = truthToKey(summary?.data?.market?.truth);
  const fundamentalsTruth = truthToKey(summary?.data?.fundamentals?.truth);
  const notificationTruth = truthToKey(summary?.notification?.truth);

  if (compact) {
    const compactSteps = (summary?.steps || []).slice(0, 3);
    return (
      <div className="mt-2 space-y-1.5 text-[11px] leading-4 text-secondary-text">
        <p className="truncate">
          {t('runtime.aiLabel')}: <span className="text-foreground">{aiModel}</span>
          <span className={`ml-1 ${TRUTH_TONE_CLASS[aiTruth]}`}>({t(`runtime.truth.${aiTruth}`)})</span>
        </p>
        <p className="truncate">
          {t('runtime.dataLabel')}: {t('runtime.marketShort')} <span className="text-foreground">{marketSource}</span>, {t('runtime.fundamentalShort')} <span className="text-foreground">{fundamentalSource}</span>
        </p>
        <p className="truncate">
          {t('runtime.newsSource')}: <span className="text-foreground">{newsSource}</span> · <span className={STATUS_TONE_CLASS[newsStatus] || STATUS_TONE_CLASS.unknown}>{t(`runtime.status.${newsStatus}`)}</span>
        </p>
        <p className="truncate">
          {t('runtime.notificationLabel')}: <span className={STATUS_TONE_CLASS[notificationStatus] || STATUS_TONE_CLASS.unknown}>{t(`runtime.status.${notificationStatus}`)}</span>
        </p>
        {compactSteps.length ? (
          <p className="truncate">
            {compactSteps.map((step) => {
              const status = String(step.status || 'unknown').toLowerCase();
              return `${t(`runtime.step.${step.key}`)} ${t(`runtime.status.${status}`)}`;
            }).join(' · ')}
          </p>
        ) : null}
      </div>
    );
  }

  return (
    <section className="theme-panel-solid rounded-[1rem] border border-border/60 p-4" data-testid="runtime-execution-summary">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-foreground">{t('runtime.title')}</h3>
        <span className="text-[11px] text-muted-text">{t('runtime.subtitle')}</span>
      </div>

      <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-lg border border-border/50 bg-muted/20 px-3 py-2">
          <p className="text-[11px] uppercase tracking-[0.08em] text-muted-text">{t('runtime.aiLabel')}</p>
          <p className="mt-1 text-sm text-foreground">{aiModel}</p>
          <p className="mt-1 text-xs text-secondary-text">{t('runtime.provider')}: {aiProvider}</p>
          <p className="text-xs text-secondary-text">{t('runtime.gateway')}: {aiGateway}</p>
          <p className={`mt-1 text-[11px] ${TRUTH_TONE_CLASS[aiTruth]}`}>{t(`runtime.truth.${aiTruth}`)}</p>
        </div>

        <div className="rounded-lg border border-border/50 bg-muted/20 px-3 py-2">
          <p className="text-[11px] uppercase tracking-[0.08em] text-muted-text">{t('runtime.marketSource')}</p>
          <p className="mt-1 text-sm text-foreground">{marketSource}</p>
          <p className={`mt-1 text-[11px] ${TRUTH_TONE_CLASS[marketTruth]}`}>{t(`runtime.truth.${marketTruth}`)}</p>
          {summary?.data?.market?.fallbackOccurred ? (
            <p className="mt-1 text-[11px] text-[hsl(var(--accent-warning-hsl))]">{t('runtime.fallbackOccurred')}</p>
          ) : null}
        </div>

        <div className="rounded-lg border border-border/50 bg-muted/20 px-3 py-2">
          <p className="text-[11px] uppercase tracking-[0.08em] text-muted-text">{t('runtime.fundamentalSource')}</p>
          <p className="mt-1 text-sm text-foreground">{fundamentalSource}</p>
          <p className="mt-1 text-xs text-secondary-text">
            {t('runtime.newsSource')}: {newsSource}
            <span className={`ml-1 ${STATUS_TONE_CLASS[newsStatus] || STATUS_TONE_CLASS.unknown}`}>
              ({t(`runtime.status.${newsStatus}`)})
            </span>
          </p>
          <p className="text-xs text-secondary-text">
            {t('runtime.sentimentSource')}: {sentimentSource}
            <span className={`ml-1 ${STATUS_TONE_CLASS[sentimentStatus] || STATUS_TONE_CLASS.unknown}`}>
              ({t(`runtime.status.${sentimentStatus}`)})
            </span>
          </p>
          <p className={`mt-1 text-[11px] ${TRUTH_TONE_CLASS[newsTruth]}`}>{t('runtime.newsSource')} {t(`runtime.truth.${newsTruth}`)}</p>
          <p className={`text-[11px] ${TRUTH_TONE_CLASS[sentimentTruth]}`}>{t('runtime.sentimentSource')} {t(`runtime.truth.${sentimentTruth}`)}</p>
          <p className={`mt-1 text-[11px] ${TRUTH_TONE_CLASS[fundamentalsTruth]}`}>{t(`runtime.truth.${fundamentalsTruth}`)}</p>
        </div>

        <div className="rounded-lg border border-border/50 bg-muted/20 px-3 py-2">
          <p className="text-[11px] uppercase tracking-[0.08em] text-muted-text">{t('runtime.notificationLabel')}</p>
          <p className={`mt-1 text-sm ${STATUS_TONE_CLASS[notificationStatus] || STATUS_TONE_CLASS.unknown}`}>
            {t(`runtime.status.${notificationStatus}`)}
          </p>
          <p className="mt-1 text-xs text-secondary-text">{t('runtime.channels')}: {notificationChannels}</p>
          <p className={`mt-1 text-[11px] ${TRUTH_TONE_CLASS[notificationTruth]}`}>{t(`runtime.truth.${notificationTruth}`)}</p>
        </div>
      </div>

      {(summary?.steps || []).length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {(summary?.steps || []).map((step) => {
            const status = String(step.status || 'unknown').toLowerCase();
            return (
              <span
                key={`${step.key}-${status}`}
                className="rounded-full border border-border/60 bg-muted/30 px-2.5 py-1 text-[11px] text-secondary-text"
              >
                {t(`runtime.step.${step.key}`)}: <span className={STATUS_TONE_CLASS[status] || STATUS_TONE_CLASS.unknown}>{t(`runtime.status.${status}`)}</span>
              </span>
            );
          })}
        </div>
      ) : (
        <p className="mt-3 text-xs text-muted-text">{fallbackText}</p>
      )}
    </section>
  );
};

export default ExecutionSummaryCard;
