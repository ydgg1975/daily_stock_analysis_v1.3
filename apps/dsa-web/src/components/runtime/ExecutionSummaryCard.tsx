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
    <section className="execution-summary theme-panel-solid" data-testid="runtime-execution-summary">
      <div className="execution-summary__header">
        <h3 className="execution-summary__title">{t('runtime.title')}</h3>
        <span className="execution-summary__subtitle">{t('runtime.subtitle')}</span>
      </div>

      <div className="execution-summary__grid">
        <div className="execution-summary__panel">
          <p className="execution-summary__kicker">{t('runtime.aiLabel')}</p>
          <p className="execution-summary__value">{aiModel}</p>
          <p className="execution-summary__meta">{t('runtime.provider')}: {aiProvider}</p>
          <p className="execution-summary__meta">{t('runtime.gateway')}: {aiGateway}</p>
          <p className={`execution-summary__truth ${TRUTH_TONE_CLASS[aiTruth]}`}>{t(`runtime.truth.${aiTruth}`)}</p>
        </div>

        <div className="execution-summary__panel">
          <p className="execution-summary__kicker">{t('runtime.marketSource')}</p>
          <p className="execution-summary__value">{marketSource}</p>
          <p className={`execution-summary__truth ${TRUTH_TONE_CLASS[marketTruth]}`}>{t(`runtime.truth.${marketTruth}`)}</p>
          {summary?.data?.market?.fallbackOccurred ? (
            <p className="execution-summary__truth text-[hsl(var(--accent-warning-hsl))]">{t('runtime.fallbackOccurred')}</p>
          ) : null}
        </div>

        <div className="execution-summary__panel">
          <p className="execution-summary__kicker">{t('runtime.fundamentalSource')}</p>
          <p className="execution-summary__value">{fundamentalSource}</p>
          <p className="execution-summary__meta">
            {t('runtime.newsSource')}: {newsSource}
            <span className={`ml-1 ${STATUS_TONE_CLASS[newsStatus] || STATUS_TONE_CLASS.unknown}`}>
              ({t(`runtime.status.${newsStatus}`)})
            </span>
          </p>
          <p className="execution-summary__meta">
            {t('runtime.sentimentSource')}: {sentimentSource}
            <span className={`ml-1 ${STATUS_TONE_CLASS[sentimentStatus] || STATUS_TONE_CLASS.unknown}`}>
              ({t(`runtime.status.${sentimentStatus}`)})
            </span>
          </p>
          <p className={`execution-summary__truth ${TRUTH_TONE_CLASS[newsTruth]}`}>{t('runtime.newsSource')} {t(`runtime.truth.${newsTruth}`)}</p>
          <p className={`execution-summary__truth ${TRUTH_TONE_CLASS[sentimentTruth]}`}>{t('runtime.sentimentSource')} {t(`runtime.truth.${sentimentTruth}`)}</p>
          <p className={`execution-summary__truth ${TRUTH_TONE_CLASS[fundamentalsTruth]}`}>{t(`runtime.truth.${fundamentalsTruth}`)}</p>
        </div>

        <div className="execution-summary__panel">
          <p className="execution-summary__kicker">{t('runtime.notificationLabel')}</p>
          <p className={`execution-summary__value ${STATUS_TONE_CLASS[notificationStatus] || STATUS_TONE_CLASS.unknown}`}>
            {t(`runtime.status.${notificationStatus}`)}
          </p>
          <p className="execution-summary__meta">{t('runtime.channels')}: {notificationChannels}</p>
          <p className={`execution-summary__truth ${TRUTH_TONE_CLASS[notificationTruth]}`}>{t(`runtime.truth.${notificationTruth}`)}</p>
        </div>
      </div>

      {(summary?.steps || []).length > 0 ? (
        <div className="execution-summary__steps">
          {(summary?.steps || []).map((step) => {
            const status = String(step.status || 'unknown').toLowerCase();
            return (
              <span
                key={`${step.key}-${status}`}
                className="execution-summary__step"
              >
                {t(`runtime.step.${step.key}`)}: <span className={STATUS_TONE_CLASS[status] || STATUS_TONE_CLASS.unknown}>{t(`runtime.status.${status}`)}</span>
              </span>
            );
          })}
        </div>
      ) : (
        <p className="execution-summary__empty">{fallbackText}</p>
      )}
    </section>
  );
};

export default ExecutionSummaryCard;
