import { useMemo, useState } from 'react';
import type React from 'react';
import { Send } from 'lucide-react';
import { getParsedApiError, type ParsedApiError } from '../../api/error';
import { systemConfigApi } from '../../api/systemConfig';
import type {
  NotificationTestChannel,
  TestNotificationChannelResponse,
  SystemConfigUpdateItem,
} from '../../types/systemConfig';
import { ApiErrorAlert, Badge, Button, InlineAlert, Input, Select } from '../common';
import { SettingsSectionCard } from './SettingsSectionCard';

const CHANNEL_OPTIONS: Array<{ value: NotificationTestChannel; label: string }> = [
  { value: 'wechat', label: 'WeCom' },
  { value: 'feishu', label: 'Feishu Webhook' },
  { value: 'telegram', label: 'Telegram' },
  { value: 'email', label: '이메일' },
  { value: 'pushover', label: 'Pushover' },
  { value: 'ntfy', label: 'ntfy' },
  { value: 'gotify', label: 'Gotify' },
  { value: 'pushplus', label: 'PushPlus' },
  { value: 'serverchan3', label: 'ServerChan3' },
  { value: 'custom', label: '사용자 정의 Webhook' },
  { value: 'discord', label: 'Discord' },
  { value: 'slack', label: 'Slack' },
  { value: 'astrbot', label: 'AstrBot' },
];

interface NotificationTestPanelProps {
  items: SystemConfigUpdateItem[];
  maskToken: string;
  disabled?: boolean;
}

function clampTimeout(value: string): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return 20;
  return Math.min(120, Math.max(1, parsed));
}

export const NotificationTestPanel: React.FC<NotificationTestPanelProps> = ({
  items,
  maskToken,
  disabled = false,
}) => {
  const [channel, setChannel] = useState<NotificationTestChannel>('wechat');
  const [title, setTitle] = useState('DSA 알림 테스트');
  const [content, setContent] = useState('DSA Web 설정 페이지에서 보낸 알림 테스트 메시지입니다.');
  const [timeoutSeconds, setTimeoutSeconds] = useState('20');
  const [result, setResult] = useState<TestNotificationChannelResponse | null>(null);
  const [error, setError] = useState<ParsedApiError | null>(null);
  const [isTesting, setIsTesting] = useState(false);

  const normalizedItems = useMemo(
    () => items.map((item) => ({ key: item.key, value: String(item.value ?? '') })),
    [items],
  );

  const runTest = async () => {
    setError(null);
    setResult(null);
    setIsTesting(true);
    try {
      const payload = await systemConfigApi.testNotificationChannel({
        channel,
        items: normalizedItems,
        maskToken,
        title: title.trim() || 'DSA 알림 테스트',
        content: content.trim() || 'DSA Web 설정 페이지에서 보낸 알림 테스트 메시지입니다.',
        timeoutSeconds: clampTimeout(timeoutSeconds),
      });
      setResult(payload);
    } catch (requestError: unknown) {
      setError(getParsedApiError(requestError));
    } finally {
      setIsTesting(false);
    }
  };

  return (
    <SettingsSectionCard
      title="알림 테스트"
      description="현재 페이지 초안으로 실제 테스트 알림을 보냅니다. 테스트는 설정을 저장하지 않습니다."
      actions={(
        <Button
          type="button"
          variant="settings-primary"
          size="sm"
          onClick={() => void runTest()}
          disabled={disabled || isTesting}
          isLoading={isTesting}
          loadingText="테스트 중..."
        >
          <Send className="h-4 w-4" />
          테스트 보내기
        </Button>
      )}
    >
      <div className="grid grid-cols-1 gap-3 md:grid-cols-[1fr_1fr_120px]">
        <Select
          label="채널"
          value={channel}
          options={CHANNEL_OPTIONS}
          disabled={disabled || isTesting}
          onChange={(value) => setChannel(value as NotificationTestChannel)}
        />
        <Input
          label="제목"
          value={title}
          maxLength={80}
          disabled={disabled || isTesting}
          onChange={(event) => setTitle(event.target.value)}
        />
        <Input
          label="제한 시간(초)"
          type="number"
          min={1}
          max={120}
          value={timeoutSeconds}
          disabled={disabled || isTesting}
          onChange={(event) => setTimeoutSeconds(event.target.value)}
          onBlur={() => setTimeoutSeconds(String(clampTimeout(timeoutSeconds)))}
        />
      </div>

      <label className="block">
        <span className="mb-2 block text-sm font-medium text-foreground">본문</span>
        <textarea
          value={content}
          maxLength={1000}
          rows={4}
          disabled={disabled || isTesting}
          onChange={(event) => setContent(event.target.value)}
          className="input-surface input-focus-glow min-h-[112px] w-full resize-y rounded-xl border bg-transparent px-4 py-3 text-sm leading-6 text-foreground outline-none disabled:cursor-not-allowed disabled:opacity-50"
        />
      </label>

      {error ? <ApiErrorAlert error={error} /> : null}

      {result ? (
        <div className="space-y-3">
          <InlineAlert
            variant={result.success ? 'success' : 'danger'}
            title={result.success ? '테스트 성공' : '테스트 실패'}
            message={(
              <span>
                {result.message}
                {typeof result.latencyMs === 'number' ? ` · ${result.latencyMs} ms` : ''}
                {result.errorCode ? ` · ${result.errorCode}` : ''}
              </span>
            )}
          />

          {result.attempts.length ? (
            <div className="space-y-2">
              {result.attempts.map((attempt, index) => (
                <div
                  key={`${attempt.channel}-${index}-${attempt.target || 'target'}`}
                  className="rounded-xl border settings-border bg-background/35 px-4 py-3"
                >
                  <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant={attempt.success ? 'success' : 'danger'}>
                          {attempt.success ? '성공' : '실패'}
                        </Badge>
                        <span className="text-sm font-medium text-foreground">
                          Attempt {index + 1}
                        </span>
                        {typeof attempt.httpStatus === 'number' ? (
                          <span className="text-xs text-muted-text">HTTP {attempt.httpStatus}</span>
                        ) : null}
                        {typeof attempt.latencyMs === 'number' ? (
                          <span className="text-xs text-muted-text">{attempt.latencyMs} ms</span>
                        ) : null}
                      </div>
                      <p className="mt-2 break-all text-xs leading-5 text-muted-text">
                        {attempt.target || attempt.channel}
                      </p>
                    </div>
                    {attempt.errorCode ? (
                      <Badge variant={attempt.retryable ? 'warning' : 'default'}>
                        {attempt.errorCode}
                      </Badge>
                    ) : null}
                  </div>
                  <p className="mt-2 text-xs leading-5 text-secondary-text">{attempt.message}</p>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </SettingsSectionCard>
  );
};
