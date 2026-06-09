import type React from 'react';
import { useCallback, useEffect, useState } from 'react';
import { SYSTEM_CONFIG_CHANGED_EVENT } from '../../api/alphasift';
import { getParsedApiError } from '../../api/error';
import { systemConfigApi } from '../../api/systemConfig';
import { useUiLanguage } from '../../contexts/UiLanguageContext';
import type { SchedulerStatusResponse } from '../../types/systemConfig';
import { Badge, Button } from '../common';
import { SettingsAlert } from './SettingsAlert';
import { SettingsSectionCard } from './SettingsSectionCard';

type Notice = { message: string; variant: 'success' | 'warning' };

export const SchedulerStatusCard: React.FC = () => {
  const { t } = useUiLanguage();
  const [status, setStatus] = useState<SchedulerStatusResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);

  const loadStatus = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setStatus(await systemConfigApi.getSchedulerStatus());
    } catch (err) {
      setError(getParsedApiError(err)?.message ?? t('settings.scheduler.loadError'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void loadStatus();
    const handler = () => {
      void loadStatus();
    };
    window.addEventListener(SYSTEM_CONFIG_CHANGED_EVENT, handler);
    return () => window.removeEventListener(SYSTEM_CONFIG_CHANGED_EVENT, handler);
  }, [loadStatus]);

  const handleRunNow = useCallback(async () => {
    setTriggering(true);
    setNotice(null);
    setError(null);
    try {
      const result = await systemConfigApi.runSchedulerNow();
      setNotice({
        message: result.triggered
          ? t('settings.scheduler.runNowSuccess')
          : t('settings.scheduler.runNowSkipped'),
        variant: result.triggered ? 'success' : 'warning',
      });
      await loadStatus();
    } catch (err) {
      setError(getParsedApiError(err)?.message ?? t('settings.scheduler.loadError'));
    } finally {
      setTriggering(false);
    }
  }, [loadStatus, t]);

  const available = status?.available ?? false;
  const none = t('settings.scheduler.none');

  const renderRow = (label: string, value: React.ReactNode) => (
    <div className="flex items-start justify-between gap-3 py-1.5">
      <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-text">{label}</span>
      <span className="text-right text-sm text-foreground">{value}</span>
    </div>
  );

  return (
    <SettingsSectionCard
      title={t('settings.scheduler.title')}
      description={t('settings.scheduler.description')}
    >
      {error ? (
        <SettingsAlert title={t('settings.scheduler.loadError')} message={error} variant="error" />
      ) : null}
      {notice ? (
        <div className="mb-3">
          <SettingsAlert title={t('settings.scheduler.title')} message={notice.message} variant={notice.variant} />
        </div>
      ) : null}

      {!available ? (
        <p className="rounded-2xl border settings-border bg-background/40 px-4 py-3 text-sm text-muted-text">
          {t('settings.scheduler.unavailable')}
        </p>
      ) : (
        <div className="rounded-2xl border settings-border bg-background/40 px-4 py-3">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <Badge variant={status?.enabled ? 'success' : 'default'}>
              {status?.enabled ? t('common.enabled') : t('common.disabled')}
            </Badge>
            <Badge variant={status?.schedulerRunning ? 'success' : 'warning'}>
              {status?.schedulerRunning ? t('settings.scheduler.running') : t('settings.scheduler.stopped')}
            </Badge>
            {status?.taskRunning ? <Badge variant="info">{t('settings.scheduler.taskRunning')}</Badge> : null}
          </div>

          {renderRow(
            t('settings.scheduler.effectiveTimes'),
            status && status.scheduleTimes.length > 0 ? (
              <span className="font-mono">{status.scheduleTimes.join(', ')}</span>
            ) : (
              <span className="text-muted-text">{t('settings.scheduler.noTimes')}</span>
            ),
          )}
          {renderRow(
            t('settings.scheduler.nextRun'),
            <span className="font-mono">{status?.nextRun ?? none}</span>,
          )}
          {renderRow(
            t('settings.scheduler.lastRun'),
            status?.lastFinishedAt ? (
              <span>
                <span className="font-mono">{status.lastFinishedAt}</span>
                {status.lastSuccess === null ? null : (
                  <Badge variant={status.lastSuccess ? 'success' : 'danger'} className="ml-2">
                    {status.lastSuccess ? t('common.success') : t('common.failure')}
                  </Badge>
                )}
              </span>
            ) : (
              none
            ),
          )}
          {status?.lastError
            ? renderRow(t('settings.scheduler.lastError'), <span className="text-danger">{status.lastError}</span>)
            : null}
          {status && status.skippedCount > 0
            ? renderRow(t('settings.scheduler.skipped'), <span className="font-mono">{status.skippedCount}</span>)
            : null}
        </div>
      )}

      <div className="mt-3 flex flex-wrap gap-2">
        <Button
          variant="settings-primary"
          size="sm"
          onClick={handleRunNow}
          isLoading={triggering}
          disabled={!available || triggering}
        >
          {triggering ? t('settings.scheduler.triggering') : t('settings.scheduler.runNow')}
        </Button>
        <Button variant="settings-secondary" size="sm" onClick={() => void loadStatus()} disabled={loading}>
          {t('settings.scheduler.refresh')}
        </Button>
      </div>

      <p className="mt-3 text-xs leading-6 text-muted-text">{t('settings.scheduler.runImmediatelyNote')}</p>
    </SettingsSectionCard>
  );
};

export default SchedulerStatusCard;
