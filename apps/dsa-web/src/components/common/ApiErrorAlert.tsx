import type React from 'react';
import type { ParsedApiError } from '../../api/error';

interface ApiErrorAlertProps {
  error: ParsedApiError;
  className?: string;
  actionLabel?: string;
  onAction?: () => void;
  dismissLabel?: string;
  onDismiss?: () => void;
}

function getErrorGuidance(error: ParsedApiError): string[] {
  if (error.category === 'local_connection_failed') {
    return [
      '确认后端服务已启动，并且 Web 前端可访问同一个 API 地址。',
      '移动端访问时请检查与服务端是否在同一网络，或是否正确配置了反向代理。',
      '刷新页面后重试；若仍失败，请重新登录以刷新会话状态。',
    ];
  }

  if (error.category === 'upstream_timeout' || error.category === 'upstream_network' || error.category === 'upstream_unavailable') {
    return [
      '本地服务已连接，但外部模型或数据源不可用，请稍后重试。',
      '检查代理、DNS、API Key 配置或上游服务配额。',
    ];
  }

  if (error.category === 'analysis_conflict') {
    return [
      '同一标的已有任务在运行，等待当前任务完成后再发起新的请求。',
    ];
  }

  return [];
}

export const ApiErrorAlert: React.FC<ApiErrorAlertProps> = ({
  error,
  className = '',
  actionLabel,
  onAction,
  dismissLabel = '关闭',
  onDismiss,
}) => {
  const showDetails = error.rawMessage.trim() && error.rawMessage.trim() !== error.message.trim();
  const guidance = getErrorGuidance(error);

  return (
    <div
      className={`rounded-xl border border-red-500/35 bg-red-500/10 px-4 py-3 text-red-200 ${className}`}
      role="alert"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold">{error.title}</p>
          <p className="mt-1 text-xs opacity-90">{error.message}</p>
        </div>
        {onDismiss ? (
          <button
            type="button"
            className="shrink-0 rounded-md border border-danger/25 bg-danger/5 px-2 py-1 text-[11px] text-danger transition hover:bg-danger/12"
            onClick={onDismiss}
          >
            {dismissLabel}
          </button>
        ) : null}
      </div>
      {showDetails ? (
        <details className="mt-3 rounded-lg border border-subtle bg-surface-2 px-3 py-2">
          <summary className="cursor-pointer text-xs text-danger opacity-90">查看详情</summary>
          <pre className="mt-2 whitespace-pre-wrap break-words text-[11px] leading-5 text-danger opacity-85">
            {error.rawMessage}
          </pre>
        </details>
      ) : null}
      {guidance.length > 0 ? (
        <ul className="mt-3 space-y-1.5 rounded-lg border border-subtle bg-surface-2 px-3 py-2 text-[11px] leading-5 text-secondary-text">
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
    </div>
  );
};
