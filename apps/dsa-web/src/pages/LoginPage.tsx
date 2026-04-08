import type React from 'react';
import { useEffect, useState } from 'react';
import { Button, Input } from '../components/common';
import { useNavigate, useSearchParams } from 'react-router-dom';
import type { ParsedApiError } from '../api/error';
import { isParsedApiError } from '../api/error';
import { useAuth } from '../hooks';
import { SettingsAlert } from '../components/settings';

const AUTH_FACTS = [
  '统一研究工作台',
  '受保护的管理员会话',
  '分析、问股、持仓、回测共用同一套产品壳层',
];

const LoginPage: React.FC = () => {
  const { login, passwordSet, setupState } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    document.title = '登录 - WolfyStock';
  }, []);

  const [searchParams] = useSearchParams();
  const rawRedirect = searchParams.get('redirect') ?? '';
  const redirect =
    rawRedirect.startsWith('/') && !rawRedirect.startsWith('//') ? rawRedirect : '/';

  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | ParsedApiError | null>(null);

  const isFirstTime = setupState === 'no_password' || !passwordSet;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (isFirstTime && password !== passwordConfirm) {
      setError('两次输入的密码不一致');
      return;
    }

    setIsSubmitting(true);
    try {
      const result = await login(password, isFirstTime ? passwordConfirm : undefined);
      if (result.success) {
        navigate(redirect, { replace: true });
      } else {
        setError(result.error ?? '登录失败');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="auth-screen">
      <div className="auth-screen__backdrop" aria-hidden="true" />
      <div className="auth-screen__grid" aria-hidden="true" />

      <div className="auth-shell">
        <section className="auth-hero">
          <p className="auth-hero__eyebrow">Stock Analysis Workspace</p>
          <h1 className="auth-hero__title">
            {isFirstTime ? '设置管理员访问口令' : '授权进入研究工作台'}
          </h1>
          <p className="auth-hero__body">
            {isFirstTime
              ? '首次启用认证时，先为统一研究环境创建管理员密码。完成后即可进入分析、问股、持仓与回测工作区。'
              : '登录后即可继续使用统一的研究壳层、任务状态、报告流和回测工作区。'}
          </p>

          <div className="auth-hero__facts" role="list" aria-label="认证说明">
            {AUTH_FACTS.map((item) => (
              <div key={item} className="auth-fact" role="listitem">
                <span className="auth-fact__line" aria-hidden="true" />
                <span>{item}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="auth-panel theme-panel-glass">
          <div className="auth-panel__header">
            <p className="label-uppercase text-secondary-text">
              {isFirstTime ? 'Initial Access' : 'Secure Login'}
            </p>
            <h2 className="auth-panel__title">
              <span>{isFirstTime ? '设置初始密码' : '管理员登录'}</span>
            </h2>
            <p className="auth-panel__body">
              {isFirstTime
                ? '创建后续登录使用的管理员密码。'
                : '输入管理员密码以继续进入当前工作台。'}
            </p>
          </div>

          <form onSubmit={handleSubmit} className="auth-form">
            <Input
              id="password"
              type="password"
              allowTogglePassword
              iconType="password"
              label={isFirstTime ? '管理员密码' : '登录密码'}
              placeholder={isFirstTime ? '请设置 6 位以上密码' : '请输入密码'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={isSubmitting}
              autoFocus
              autoComplete={isFirstTime ? 'new-password' : 'current-password'}
            />

            {isFirstTime ? (
              <Input
                id="passwordConfirm"
                type="password"
                allowTogglePassword
                iconType="password"
                label="确认密码"
                placeholder="再次确认管理员密码"
                value={passwordConfirm}
                onChange={(e) => setPasswordConfirm(e.target.value)}
                disabled={isSubmitting}
                autoComplete="new-password"
              />
            ) : null}

            {error ? (
              <SettingsAlert
                title={isFirstTime ? '配置失败' : '验证未通过'}
                message={isParsedApiError(error) ? error.message : error}
                variant="error"
              />
            ) : null}

            <Button
              type="submit"
              variant="primary"
              size="xl"
              className="w-full justify-center"
              disabled={isSubmitting}
              isLoading={isSubmitting}
              loadingText={isFirstTime ? '初始化安全凭据' : '建立授权会话'}
            >
              {isFirstTime ? '完成设置并登录' : '授权进入工作台'}
            </Button>
          </form>

          <div className="auth-panel__foot">
            <span>Protected session</span>
            <span>Research workspace</span>
            <span>Calm interaction</span>
          </div>
        </section>
      </div>
    </main>
  );
};

export default LoginPage;
