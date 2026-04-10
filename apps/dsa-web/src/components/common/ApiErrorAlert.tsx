import type React from 'react';
import type { ParsedApiError } from '../../api/error';
import { useI18n } from '../../contexts/UiLanguageContext';
import { SupportBanner } from './SupportSurface';

interface ApiErrorAlertProps {
  error: ParsedApiError;
  className?: string;
  actionLabel?: string;
  onAction?: () => void;
  dismissLabel?: string;
  onDismiss?: () => void;
}

function getErrorGuidance(
  error: ParsedApiError,
  t: (key: string, vars?: Record<string, string | number | undefined>) => string,
): string[] {
  if (error.category === 'local_connection_failed') {
    return [
      t('common.apiError.guidance.localConnection1'),
      t('common.apiError.guidance.localConnection2'),
      t('common.apiError.guidance.localConnection3'),
    ];
  }

  if (error.category === 'upstream_timeout' || error.category === 'upstream_network' || error.category === 'upstream_unavailable') {
    return [
      t('common.apiError.guidance.upstream1'),
      t('common.apiError.guidance.upstream2'),
    ];
  }

  if (error.category === 'analysis_conflict') {
    return [
      t('common.apiError.guidance.analysisConflict'),
    ];
  }

  return [];
}

export const ApiErrorAlert: React.FC<ApiErrorAlertProps> = ({
  error,
  className = '',
  actionLabel,
  onAction,
  dismissLabel,
  onDismiss,
}) => {
  const { t } = useI18n();
  const showDetails = error.rawMessage.trim() && error.rawMessage.trim() !== error.message.trim();
  const guidance = getErrorGuidance(error, t);
  const dismissText = dismissLabel || t('common.apiError.close');

  return (
    <SupportBanner
      tone="danger"
      title={(
        <div className="flex items-start justify-between gap-3">
          <span>{error.title}</span>
          {onDismiss ? (
            <button
              type="button"
              className="shrink-0 rounded-[var(--theme-button-radius)] border border-[var(--state-danger-border)] bg-[var(--state-danger-bg)] px-2.5 py-1 text-[11px] uppercase tracking-[0.14em] text-[var(--state-danger-text)] transition hover:bg-[var(--state-danger-bg-strong)]"
              onClick={onDismiss}
            >
              {dismissText}
            </button>
          ) : null}
        </div>
      )}
      body={error.message}
      titleClassName="text-danger"
      bodyClassName="text-danger opacity-90"
      className={className}
      role="alert"
    >
      {showDetails ? (
        <details className="theme-panel-subtle mt-3 rounded-[var(--cohere-radius-medium)] px-3 py-3">
          <summary className="label-uppercase cursor-pointer text-danger opacity-90">{t('common.apiError.details')}</summary>
          <pre className="mt-2 whitespace-pre-wrap break-words text-[11px] leading-5 text-danger opacity-85">
            {error.rawMessage}
          </pre>
        </details>
      ) : null}
      {guidance.length > 0 ? (
        <ul className="theme-panel-subtle mt-3 space-y-1.5 rounded-[var(--cohere-radius-medium)] px-3 py-3 text-[11px] leading-5 text-secondary-text">
          {guidance.map((entry) => (
            <li key={entry}>• {entry}</li>
          ))}
        </ul>
      ) : null}
      {actionLabel && onAction ? (
        <button type="button" className="mt-3 btn-secondary !px-3 !py-1.5 !text-xs" onClick={onAction}>
          {actionLabel}
        </button>
      ) : null}
    </SupportBanner>
  );
};
