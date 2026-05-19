import type React from 'react';
import { useState } from 'react';
import type { ParsedApiError } from '../../api/error';
import { isParsedApiError } from '../../api/error';
import { useAuth } from '../../hooks';
import { Button, Input } from '../common';
import { SettingsAlert } from './SettingsAlert';
import { SettingsSectionCard } from './SettingsSectionCard';

export const ChangePasswordCard: React.FC = () => {
  const { changePassword } = useAuth();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newPasswordConfirm, setNewPasswordConfirm] = useState('');
  
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | ParsedApiError | null>(null);
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(false);

    if (!currentPassword.trim()) {
      setError('현재 비밀번호를 입력하세요');
      return;
    }
    if (!newPassword.trim()) {
      setError('새 비밀번호를 입력하세요');
      return;
    }
    if (newPassword.length < 6) {
      setError('새 비밀번호는 최소 6자여야 합니다');
      return;
    }
    if (newPassword !== newPasswordConfirm) {
      setError('두 번 입력한 새 비밀번호가 일치하지 않습니다');
      return;
    }

    setIsSubmitting(true);
    try {
      const result = await changePassword(currentPassword, newPassword, newPasswordConfirm);
      if (result.success) {
        setSuccess(true);
        setCurrentPassword('');
        setNewPassword('');
        setNewPasswordConfirm('');
        setTimeout(() => setSuccess(false), 4000);
      } else {
        setError(result.error ?? '변경 실패');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <SettingsSectionCard
      title="비밀번호 변경"
      description="현재 관리자 로그인 비밀번호를 업데이트합니다. 변경 후에는 새 비밀번호로 로그인하세요."
    >
      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-3">
            <Input
              id="change-pass-current"
              type="password"
              allowTogglePassword
              iconType="password"
              label="현재 비밀번호"
              placeholder="현재 비밀번호 입력"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              disabled={isSubmitting}
              autoComplete="current-password"
            />
          </div>

          <div className="space-y-3">
            <Input
              id="change-pass-new"
              type="password"
              allowTogglePassword
              iconType="password"
              label="새 비밀번호"
              hint="최소 6자."
              placeholder="새 비밀번호 입력"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              disabled={isSubmitting}
              autoComplete="new-password"
            />
          </div>
        </div>

        <div className="space-y-3 md:max-w-md">
          <Input
            id="change-pass-confirm"
            type="password"
            allowTogglePassword
            iconType="password"
            label="새 비밀번호 확인"
            placeholder="새 비밀번호 다시 입력"
            value={newPasswordConfirm}
            onChange={(e) => setNewPasswordConfirm(e.target.value)}
            disabled={isSubmitting}
            autoComplete="new-password"
          />
        </div>

        {error
          ? isParsedApiError(error)
            ? <SettingsAlert title="변경 실패" message={error.message} variant="error" className="!mt-3" />
            : <SettingsAlert title="변경 실패" message={error} variant="error" className="!mt-3" />
          : null}
        {success ? (
          <SettingsAlert title="변경 성공" message="관리자 비밀번호가 업데이트되었습니다." variant="success" />
        ) : null}

        <Button type="submit" variant="primary" isLoading={isSubmitting}>
          새 비밀번호 저장
        </Button>
      </form>
    </SettingsSectionCard>
  );
};
