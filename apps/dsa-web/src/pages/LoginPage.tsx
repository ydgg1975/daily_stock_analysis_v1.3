import type React from 'react';
import { useEffect, useState } from 'react';
import { Button, Input } from '../components/common';
import { useNavigate, useSearchParams } from 'react-router-dom';
import type { ParsedApiError } from '../api/error';
import { isParsedApiError } from '../api/error';
import { useAuth } from '../hooks';
import { SettingsAlert } from '../components/settings';
import { normalizeRedirectPath } from '../hooks/useProductSurface';
import { buildLocalizedPath, parseLocaleFromPathname, stripLocalePrefix } from '../utils/localeRouting';

const AUTH_FACTS = [
  '统一研究工作台',
  '用户身份感知的受保护会话',
  '分析、问股、持仓、回测共用同一套产品壳层',
];

function describeRedirectTarget(pathname: string): {
  label: string;
  requiresAdmin: boolean;
} {
  if (pathname.startsWith('/settings/system')) {
    return { label: '系统设置', requiresAdmin: true };
  }
  if (pathname.startsWith('/admin/logs')) {
    return { label: '管理员日志中心', requiresAdmin: true };
  }
  if (pathname.startsWith('/chat')) {
    return { label: '问股工作台', requiresAdmin: false };
  }
  if (pathname.startsWith('/portfolio')) {
    return { label: '个人持仓工作区', requiresAdmin: false };
  }
  if (pathname.startsWith('/backtest/results/')) {
    return { label: '已保存的回测结果', requiresAdmin: false };
  }
  if (pathname.startsWith('/backtest')) {
    return { label: '回测工作区', requiresAdmin: false };
  }
  if (pathname.startsWith('/scanner')) {
    return { label: '扫描器工作区', requiresAdmin: false };
  }
  if (pathname.startsWith('/settings')) {
    return { label: '个人设置', requiresAdmin: false };
  }
  return { label: '首页研究工作台', requiresAdmin: false };
}

function describeExitTarget(
  pathname: string,
  routeLanguage: ReturnType<typeof parseLocaleFromPathname>,
): {
  label: string;
  destination: string;
  description: string;
} {
  const localize = (path: string) => (routeLanguage ? buildLocalizedPath(path, routeLanguage) : path);
  if (pathname.startsWith('/scanner')) {
    return {
      label: '返回扫描器预览',
      destination: localize('/scanner'),
      description: '先回到公开可见的扫描器预览，再决定是否登录进入个人或管理员工作区。',
    };
  }
  return {
    label: '返回首页',
    destination: localize('/'),
    description: '回到公开产品首页，不会影响后续再次登录或注册。',
  };
}

const LoginPage: React.FC = () => {
  const { login, passwordSet, setupState } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    document.title = '登录 - WolfyStock';
  }, []);

  const [searchParams] = useSearchParams();
  const redirect = normalizeRedirectPath(searchParams.get('redirect'), '/');
  const createModeRequested = searchParams.get('mode') === 'create';
  const routeLanguage = parseLocaleFromPathname(redirect) || parseLocaleFromPathname(window.location.pathname);
  const normalizedRedirect = stripLocalePrefix(redirect);
  const redirectTarget = describeRedirectTarget(normalizedRedirect);
  const exitTarget = describeExitTarget(normalizedRedirect, routeLanguage);

  const [username, setUsername] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [createUser, setCreateUser] = useState(createModeRequested);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | ParsedApiError | null>(null);

  const isAdminBootstrap = setupState === 'no_password' || !passwordSet;
  const isCreateUserMode = !isAdminBootstrap && createUser;

  useEffect(() => {
    if (!isAdminBootstrap) {
      setCreateUser(createModeRequested);
    }
  }, [createModeRequested, isAdminBootstrap]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!isAdminBootstrap && isCreateUserMode && !username.trim()) {
      setError('请输入用户名');
      return;
    }

    if ((isAdminBootstrap || isCreateUserMode) && password !== passwordConfirm) {
      setError('两次输入的密码不一致');
      return;
    }

    setIsSubmitting(true);
    try {
      const result = await login({
        username: isAdminBootstrap ? 'admin' : (username.trim() || 'admin'),
        displayName: isCreateUserMode ? displayName.trim() : undefined,
        password,
        passwordConfirm: isAdminBootstrap || isCreateUserMode ? passwordConfirm : undefined,
        createUser: isCreateUserMode,
      });
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
            {isAdminBootstrap ? '设置管理员访问口令' : isCreateUserMode ? '创建研究账户' : '登录进入研究工作台'}
          </h1>
          <p className="auth-hero__body">
            {isAdminBootstrap
              ? '首次启用认证时，先为统一研究环境创建管理员密码。完成后即可进入分析、问股、持仓与回测工作区。'
              : isCreateUserMode
                ? '创建一个最小账户后即可进入当前工作台。该阶段仅提供基础登录与个人数据归属能力。'
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
              {isAdminBootstrap ? 'Initial Access' : isCreateUserMode ? 'Create Account' : 'Secure Login'}
            </p>
            <h2 className="auth-panel__title">
              <span>{isAdminBootstrap ? '设置初始密码' : isCreateUserMode ? '创建账户并登录' : '账户登录'}</span>
            </h2>
            <p className="auth-panel__body">
              {isAdminBootstrap
                ? '创建后续登录使用的管理员密码。'
                : isCreateUserMode
                  ? '输入用户名与密码，立即创建普通用户账户。'
                  : '输入用户名和密码以继续进入当前工作台。'}
            </p>
          </div>

          <form onSubmit={handleSubmit} className="auth-form">
            {redirect !== '/' ? (
              <div className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/45 px-4 py-3">
                <p className="text-[11px] uppercase tracking-[0.14em] text-secondary-text">Continue After Sign-in</p>
                <p className="mt-2 text-sm font-semibold text-foreground">
                  登录后将继续进入：{redirectTarget.label}
                </p>
                <p className="mt-1 text-xs leading-5 text-secondary-text">
                  {redirectTarget.requiresAdmin
                    ? '如果目标页面仍然要求管理员身份，登录后系统会继续提示你使用正确账户。'
                    : '建立会话成功后，系统会自动把你带回刚才尝试访问的工作区。'}
                </p>
              </div>
            ) : null}

            <div className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/35 px-4 py-3">
              <p className="text-[11px] uppercase tracking-[0.14em] text-secondary-text">Leave Auth Page</p>
              <p className="mt-2 text-sm font-semibold text-foreground">{exitTarget.label}</p>
              <p className="mt-1 text-xs leading-5 text-secondary-text">{exitTarget.description}</p>
              <button
                type="button"
                className="btn-ghost mt-3 w-full justify-center"
                onClick={() => navigate(exitTarget.destination, { replace: true })}
                disabled={isSubmitting}
              >
                {exitTarget.label}
              </button>
            </div>

            {!isAdminBootstrap ? (
              <Input
                id="username"
                type="text"
                label="用户名"
                placeholder={isCreateUserMode ? '请输入用户名' : '留空则登录 admin'}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                disabled={isSubmitting}
                autoFocus
                autoComplete="username"
              />
            ) : null}

            {isCreateUserMode ? (
              <Input
                id="displayName"
                type="text"
                label="显示名称"
                placeholder="可选，用于界面显示"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                disabled={isSubmitting}
                autoComplete="nickname"
              />
            ) : null}

            <Input
              id="password"
              type="password"
              allowTogglePassword
              iconType="password"
              label={isAdminBootstrap ? '管理员密码' : '登录密码'}
              placeholder={isAdminBootstrap ? '请设置 6 位以上密码' : '请输入密码'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={isSubmitting}
              autoComplete={isAdminBootstrap || isCreateUserMode ? 'new-password' : 'current-password'}
            />

            {isAdminBootstrap || isCreateUserMode ? (
              <Input
                id="passwordConfirm"
                type="password"
                allowTogglePassword
                iconType="password"
                label="确认密码"
                placeholder={isAdminBootstrap ? '再次确认管理员密码' : '再次确认登录密码'}
                value={passwordConfirm}
                onChange={(e) => setPasswordConfirm(e.target.value)}
                disabled={isSubmitting}
                autoComplete="new-password"
              />
            ) : null}

            {error ? (
              <SettingsAlert
                title={isAdminBootstrap ? '配置失败' : '验证未通过'}
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
              loadingText={isAdminBootstrap ? '初始化安全凭据' : isCreateUserMode ? '创建账户并建立会话' : '建立授权会话'}
            >
              {isAdminBootstrap ? '完成设置并登录' : isCreateUserMode ? '创建账户并登录' : '授权进入工作台'}
            </Button>

            {!isAdminBootstrap ? (
              <button
                type="button"
                className="btn-ghost w-full justify-center"
                onClick={() => {
                  setCreateUser((value) => !value);
                  setPasswordConfirm('');
                  setError(null);
                }}
                disabled={isSubmitting}
              >
                {isCreateUserMode ? '已有账户，返回登录' : '没有账户？立即创建'}
              </button>
            ) : null}
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
