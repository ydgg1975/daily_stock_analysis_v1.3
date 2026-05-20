import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { authApi } from '../../api/auth';
import { getParsedApiError, isParsedApiError, type ParsedApiError } from '../../api/error';
import { useAuth } from '../../hooks';
import { Badge, Button, Checkbox, Input } from '../common';
import { SettingsAlert } from './SettingsAlert';
import { SettingsSectionCard } from './SettingsSectionCard';

function createNextModeLabel(authEnabled: boolean, desiredEnabled: boolean) {
  if (authEnabled && !desiredEnabled) {
    return '인증 끄기';
  }
  if (!authEnabled && desiredEnabled) {
    return '인증 켜기';
  }
  return authEnabled ? '켜진 상태 유지' : '꺼진 상태 유지';
}

export const AuthSettingsCard: React.FC = () => {
  const { authEnabled, setupState, refreshStatus } = useAuth();
  const [desiredEnabled, setDesiredEnabled] = useState(authEnabled);
  const [currentPassword, setCurrentPassword] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | ParsedApiError | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const isDirty = desiredEnabled !== authEnabled || currentPassword || password || passwordConfirm;
  const targetActionLabel = createNextModeLabel(authEnabled, desiredEnabled);

  const helperText = useMemo(() => {
    switch (setupState) {
      case 'no_password':
        return '시스템에 아직 비밀번호가 없습니다. 인증을 켜기 전에 초기 관리자 비밀번호를 설정하고 안전하게 보관하세요.';
      case 'password_retained':
        return '시스템에 이전 관리자 비밀번호가 보관되어 있습니다. 현재 비밀번호를 입력하면 인증을 다시 켤 수 있습니다.';
      case 'enabled':
        return !desiredEnabled
          ? '현재 로그인 세션이 유효하면 인증을 바로 끌 수 있습니다. 세션이 만료되었다면 현재 관리자 비밀번호를 입력하세요.'
          : '관리자 인증이 활성화되어 있습니다. 비밀번호를 변경하려면 아래의 비밀번호 변경 기능을 사용하세요.';
      default:
        return '관리자 인증은 Web 설정 페이지와 API를 보호해 무단 접근을 막습니다.';
    }
  }, [setupState, desiredEnabled]);

  useEffect(() => {
    setDesiredEnabled(authEnabled);
  }, [authEnabled]);

  const resetForm = () => {
    setCurrentPassword('');
    setPassword('');
    setPasswordConfirm('');
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setSuccessMessage(null);

    if (setupState === 'no_password' && desiredEnabled) {
      if (!password) {
        setError('새 비밀번호는 필수입니다.');
        return;
      }
      if (password !== passwordConfirm) {
        setError('두 번 입력한 비밀번호가 일치하지 않습니다.');
        return;
      }
    }

    setIsSubmitting(true);
    try {
      await authApi.updateSettings(
        desiredEnabled,
        password.trim() || undefined,
        passwordConfirm.trim() || undefined,
        currentPassword.trim() || undefined,
      );
      await refreshStatus();
      setSuccessMessage(desiredEnabled ? '인증 설정이 업데이트되었습니다.' : '인증을 껐습니다.');
      resetForm();
    } catch (err: unknown) {
      setError(getParsedApiError(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <SettingsSectionCard
      title="인증 및 로그인 보호"
      description="관리자 비밀번호 인증을 관리해 시스템 설정을 보호합니다."
      actions={(
        <Badge
          variant={authEnabled ? 'success' : 'default'}
          size="sm"
          className={authEnabled ? '' : 'border-[var(--settings-border)] bg-[var(--settings-surface-hover)] text-secondary-text'}
        >
          {authEnabled ? '활성화됨' : '비활성화됨'}
        </Badge>
      )}
    >
      <form className="space-y-4" onSubmit={handleSubmit}>
        <div className="rounded-xl border border-[var(--settings-border)] bg-[var(--settings-surface)] p-4 shadow-soft-card transition-[background-color,border-color] duration-200 hover:border-[var(--settings-border-strong)] hover:bg-[var(--settings-surface-hover)]">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1">
              <p className="text-sm font-semibold text-foreground">관리자 인증</p>
              <p className="text-xs leading-6 text-muted-text">{helperText}</p>
            </div>
            <Checkbox
              checked={desiredEnabled}
              disabled={isSubmitting}
              label={desiredEnabled ? '켜기' : '끄기'}
              onChange={(event) => setDesiredEnabled(event.target.checked)}
              containerClassName="rounded-full border border-[var(--settings-border)] bg-[var(--settings-surface-hover)] px-4 py-2 shadow-soft-card transition-[background-color,border-color] duration-200 hover:border-[var(--settings-border-strong)] hover:bg-[var(--settings-surface)]"
            />
          </div>
        </div>

        {(desiredEnabled || (authEnabled && !desiredEnabled)) && (
          <div className="grid gap-4 md:grid-cols-2">
            {(setupState === 'password_retained' && desiredEnabled)
            || (setupState === 'enabled' && !desiredEnabled) ? (
              <div className="space-y-3">
                <Input
                  label="현재 관리자 비밀번호"
                  type="password"
                  allowTogglePassword
                  iconType="password"
                  value={currentPassword}
                  onChange={(event) => setCurrentPassword(event.target.value)}
                  autoComplete="current-password"
                  disabled={isSubmitting}
                  placeholder="현재 비밀번호를 입력하세요"
                  hint={setupState === 'password_retained' ? '인증을 다시 활성화하려면 기존 비밀번호를 입력하세요.' : '인증을 끄기 전에 신원 확인이 필요할 수 있습니다.'}
                />
              </div>
            ) : null}

            {setupState === 'no_password' && desiredEnabled ? (
              <>
                <div className="space-y-3">
                  <Input
                    label="관리자 비밀번호 설정"
                    type="password"
                    allowTogglePassword
                    iconType="password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    autoComplete="new-password"
                    disabled={isSubmitting}
                    placeholder="새 비밀번호 입력(최소 6자)"
                  />
                </div>
                <div className="space-y-3">
                  <Input
                    label="새 비밀번호 확인"
                    type="password"
                    allowTogglePassword
                    iconType="password"
                    value={passwordConfirm}
                    onChange={(event) => setPasswordConfirm(event.target.value)}
                    autoComplete="new-password"
                    disabled={isSubmitting}
                    placeholder="확인을 위해 다시 입력"
                  />
                </div>
              </>
            ) : null}
          </div>
        )}

        {error ? (
          isParsedApiError(error) ? (
            <SettingsAlert title="인증 설정 실패" message={error.message} variant="error" />
          ) : (
            <SettingsAlert title="인증 설정 실패" message={error} variant="error" />
          )
        ) : null}

        {successMessage ? (
          <SettingsAlert title="작업 성공" message={successMessage} variant="success" />
        ) : null}

        <div className="flex flex-wrap items-center gap-2">
          <Button type="submit" variant="settings-primary" isLoading={isSubmitting} disabled={!isDirty}>
            {targetActionLabel}
          </Button>
          <Button
            type="button"
            variant="settings-secondary"
            onClick={() => {
              setDesiredEnabled(authEnabled);
              setError(null);
              setSuccessMessage(null);
              resetForm();
            }}
            disabled={isSubmitting || !isDirty}
          >
            되돌리기
          </Button>
        </div>
      </form>
    </SettingsSectionCard>
  );
};
