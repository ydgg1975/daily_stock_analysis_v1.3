import { render, screen, waitFor } from '@testing-library/react';
import type { ReactElement } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SettingsPanelErrorBoundary } from '../SettingsPanelErrorBoundary';

function ThrowingPanel({ message = 'mock settings panel crash' }: { message?: string }): ReactElement {
  throw new Error(message);
}

describe('SettingsPanelErrorBoundary', () => {
  beforeEach(() => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders a configurable desktop-log diagnostic fallback when a settings panel throws', () => {
    render(
      <SettingsPanelErrorBoundary
        title="알림 설정"
        resetKey="notification"
        diagnosticHint={(
          <>
            데스크톱 진단 로그
            <code>desktop.log</code>
            와 릴리스 버전, Windows 버전, 실행 경로를 함께 제공해 주세요.
          </>
        )}
      >
        <ThrowingPanel />
      </SettingsPanelErrorBoundary>
    );

    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText('알림 설정 불러오기 실패')).toBeInTheDocument();
    expect(screen.getByText('desktop.log')).toBeInTheDocument();
    expect(screen.getByText(/릴리스 버전, Windows 버전, 실행 경로/)).toBeInTheDocument();
    expect(screen.getByText(/오류 요약: mock settings panel crash/)).toBeInTheDocument();
  });

  it('redacts and truncates sensitive error summary text', () => {
    render(
      <SettingsPanelErrorBoundary title="알림 설정" resetKey="notification">
        <ThrowingPanel
          message={`Webhook failed: https://hooks.slack.com/services/T000/B000/path-secret?token=super-secret-token&foo=bar OPENAI_API_KEY=sk-supersecretvalue123456 ${'x'.repeat(220)}`}
        />
      </SettingsPanelErrorBoundary>
    );

    const summary = screen.getByText(/오류 요약:/).textContent ?? '';

    expect(summary).toContain('https://hooks.slack.com/[redacted]?[redacted]');
    expect(summary).toContain('?[redacted]');
    expect(summary).toContain('OPENAI_API_KEY=[redacted]');
    expect(summary).not.toContain('/services/T000/B000/path-secret');
    expect(summary).not.toContain('path-secret');
    expect(summary).not.toContain('super-secret-token');
    expect(summary).not.toContain('sk-supersecretvalue123456');
    expect(summary.length).toBeLessThanOrEqual('오류 요약: '.length + 183);
  });

  it('resets after resetKey changes so the panel can render again', async () => {
    const { rerender } = render(
      <SettingsPanelErrorBoundary title="Agent 설정" resetKey="agent:v1">
        <ThrowingPanel />
      </SettingsPanelErrorBoundary>
    );

    expect(screen.getByText('Agent 설정 불러오기 실패')).toBeInTheDocument();

    rerender(
      <SettingsPanelErrorBoundary title="Agent 설정" resetKey="agent:v2">
        <div>Agent 설정이 복구되었습니다</div>
      </SettingsPanelErrorBoundary>
    );

    await waitFor(() => {
      expect(screen.getByText('Agent 설정이 복구되었습니다')).toBeInTheDocument();
    });
    expect(screen.queryByText('Agent 설정 불러오기 실패')).not.toBeInTheDocument();
  });
});
