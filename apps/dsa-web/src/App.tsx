import type React from 'react';
import { useEffect, useRef, useState } from 'react';
import { BrowserRouter as Router, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import ScannerSurfacePage from './pages/ScannerSurfacePage';
import BacktestPage from './pages/BacktestPage';
import DeterministicBacktestResultPage from './pages/DeterministicBacktestResultPage';
import SettingsPage from './pages/SettingsPage';
import LoginPage from './pages/LoginPage';
import NotFoundPage from './pages/NotFoundPage';
import ChatPage from './pages/ChatPage';
import PortfolioPage from './pages/PortfolioPage';
import PreviewReportPage from './pages/PreviewReportPage';
import PreviewFullReportDrawerPage from './pages/PreviewFullReportDrawerPage';
import AdminLogsPage from './pages/AdminLogsPage';
import { ApiErrorAlert, BrandedLoadingScreen, Shell } from './components/common';
import { AccessGatePage } from './components/access/AccessGatePage';
import { PreviewShell } from './components/layout/PreviewShell';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { useI18n } from './contexts/UiLanguageContext';
import {
  buildLoginPath,
  buildRegistrationPath,
  resolveAuthRedirect,
  useProductSurface,
} from './hooks/useProductSurface';
import type { UiLanguage } from './i18n/core';
import HomeSurfacePage from './pages/HomeSurfacePage';
import PersonalSettingsPage from './pages/PersonalSettingsPage';
import { useAgentChatStore } from './stores/agentChatStore';

const APP_BOOT_SPLASH_MIN_MS = 950;
const APP_BOOT_SPLASH_FADE_MS = 380;
const STATIC_BOOT_SPLASH_ID = 'boot-splash';

type GateCopy = {
  eyebrow: string;
  title: string;
  description: string;
  bullets: string[];
  statusLabel?: string;
  note?: string;
  secondaryAction?: { label: string; to: string };
  tertiaryAction?: { label: string; to: string };
};

function getRegisteredSurfaceCopy(pathname: string, redirectTarget: string, language: UiLanguage): GateCopy {
  const isEnglish = language === 'en';

  if (pathname.startsWith('/chat')) {
    return {
      eyebrow: isEnglish ? 'Registered User Only' : '仅限注册用户',
      statusLabel: isEnglish ? 'Guest Preview Only' : '仅限游客预览',
      title: isEnglish ? 'Sign in to continue Ask Stock follow-up' : '登录后继续问股追问',
      description: isEnglish
        ? 'Follow-up chat depends on a real account identity so report context, conversation memory, and saved sessions stay attached to you.'
        : '问股追问依赖真实账户身份，这样报告上下文、会话记忆和保存记录才会稳定绑定到你本人。',
      bullets: isEnglish
        ? [
          'Guest mode intentionally stops at preview analysis and locked teaser surfaces.',
          'Authenticated chat sessions reuse your own saved report context and conversation history.',
          'Backend ownership and authorization rules remain the source of truth.',
        ]
        : [
          '游客模式刻意停留在分析预览与锁定态产品预告，不直接进入深度问股。',
          '登录后的问股会复用你自己的报告上下文和会话历史。',
          '真实的数据归属与访问控制仍以后端规则为准。',
        ],
      note: isEnglish
        ? 'After sign-in, we will return you to this workflow automatically.'
        : '登录成功后，系统会自动把你带回当前工作流。',
      secondaryAction: {
        label: isEnglish ? 'Create account' : '创建账户',
        to: buildRegistrationPath(redirectTarget),
      },
      tertiaryAction: {
        label: isEnglish ? 'Back to guest preview' : '返回游客预览',
        to: '/',
      },
    };
  }

  if (pathname.startsWith('/portfolio')) {
    return {
      eyebrow: isEnglish ? 'Registered User Only' : '仅限注册用户',
      statusLabel: isEnglish ? 'Personal Data Required' : '需要个人数据身份',
      title: isEnglish ? 'Sign in to open your portfolio workspace' : '登录后进入你的持仓工作区',
      description: isEnglish
        ? 'Portfolio accounts, trades, cash events, and risk snapshots are all owner-scoped and are never exposed to guest mode.'
        : '持仓账户、交易、资金流水和风险快照都属于个人 owner 范围，游客模式不会暴露这些数据。',
      bullets: isEnglish
        ? [
          'Portfolio data is personal and stays tied to authenticated ownership.',
          'Guest mode does not create shared ledgers or placeholder portfolio state.',
          'Use sign-in or account creation to continue with a real workspace.',
        ]
        : [
          '持仓数据属于个人空间，只会绑定到已认证身份。',
          '游客模式不会创建共享账本或伪造持仓状态。',
          '请登录或创建账户后继续使用真实工作区。',
        ],
      note: isEnglish
        ? 'After sign-in, you will return here with your own workspace context.'
        : '登录成功后，你会带着自己的工作区上下文回到这里。',
      secondaryAction: {
        label: isEnglish ? 'Create account' : '创建账户',
        to: buildRegistrationPath(redirectTarget),
      },
      tertiaryAction: {
        label: isEnglish ? 'Back to guest preview' : '返回游客预览',
        to: '/',
      },
    };
  }

  if (pathname.startsWith('/backtest/results/')) {
    return {
      eyebrow: isEnglish ? 'Registered User Only' : '仅限注册用户',
      statusLabel: isEnglish ? 'Saved Result Locked' : '已保存结果已锁定',
      title: isEnglish ? 'Sign in to reopen saved backtest results' : '登录后重新打开已保存的回测结果',
      description: isEnglish
        ? 'Historical backtest results remain bound to authenticated identity so one user never reopens another user’s saved run.'
        : '历史回测结果会绑定到已认证身份，避免一个用户重新打开另一个用户保存的 run。',
      bullets: isEnglish
        ? [
          'Backtest results and history are protected by ownership-aware backend rules.',
          'Guest mode does not expose saved run details or historical metrics.',
          'Sign in to continue exactly where your own research workspace left off.',
        ]
        : [
          '回测结果与历史已经由 owner-aware 后端规则保护。',
          '游客模式不会暴露已保存 run 的细节和历史指标。',
          '登录后可以从你自己的研究工作区继续接着看。',
        ],
      note: isEnglish
        ? 'If this result belongs to another account, the backend will continue to block access after sign-in.'
        : '如果这个结果属于其他账户，登录后后端仍会继续阻止访问。',
      secondaryAction: {
        label: isEnglish ? 'Create account' : '创建账户',
        to: buildRegistrationPath(redirectTarget),
      },
      tertiaryAction: {
        label: isEnglish ? 'Open scanner teaser' : '查看扫描器预告',
        to: '/scanner',
      },
    };
  }

  if (pathname.startsWith('/backtest')) {
    return {
      eyebrow: isEnglish ? 'Registered User Only' : '仅限注册用户',
      statusLabel: isEnglish ? 'Workspace Locked' : '工作区已锁定',
      title: isEnglish ? 'Sign in to open the backtest workspace' : '登录后进入回测工作区',
      description: isEnglish
        ? 'Backtests, saved result history, and follow-up analysis all depend on a real user identity.'
        : '回测、已保存结果历史和后续分析都依赖真实用户身份。',
      bullets: isEnglish
        ? [
          'Guest mode intentionally stops before persistent deterministic workflows.',
          'Signed-in users can run and revisit their own backtests without shared state.',
          'Ownership and authorization continue to be enforced by the backend.',
        ]
        : [
          '游客模式刻意停在持久化确定性工作流之前。',
          '登录用户可以运行并重新查看属于自己的回测结果，而不是共享状态。',
          '真实归属与授权仍继续由后端执行。',
        ],
      note: isEnglish
        ? 'After sign-in, we will take you back to the backtest workspace.'
        : '登录成功后，系统会把你带回回测工作区。',
      secondaryAction: {
        label: isEnglish ? 'Create account' : '创建账户',
        to: buildRegistrationPath(redirectTarget),
      },
      tertiaryAction: {
        label: isEnglish ? 'Open scanner teaser' : '查看扫描器预告',
        to: '/scanner',
      },
    };
  }

  return {
    eyebrow: isEnglish ? 'Registered User Only' : '仅限注册用户',
    statusLabel: isEnglish ? 'Guest Preview Only' : '仅限游客预览',
    title: isEnglish ? 'Sign in to continue deeper workflows' : '登录后继续深度工作流',
    description: isEnglish
      ? 'This surface depends on a real user identity for ownership, saved history, and account-aware workflows.'
      : '这个页面依赖真实用户身份来承载归属、保存历史与账户感知工作流。',
    bullets: isEnglish
      ? [
        'Chat, portfolio, backtests, and saved history stay bound to authenticated users.',
        'Guest mode is intentionally limited to preview flows and locked product teasers.',
        'Backend ownership and authorization rules remain the source of truth.',
      ]
      : [
        '问股、持仓、回测和保存历史都必须绑定到已认证用户。',
        '游客模式刻意只保留预览流和锁定态产品预告。',
        '真实的数据归属与访问控制仍以后端规则为准。',
      ],
    note: isEnglish
      ? 'After sign-in, we will return you to this surface automatically.'
      : '登录成功后，系统会自动把你带回当前页面。',
    secondaryAction: {
      label: isEnglish ? 'Create account' : '创建账户',
      to: buildRegistrationPath(redirectTarget),
    },
    tertiaryAction: {
      label: isEnglish ? 'Back to guest preview' : '返回游客预览',
      to: '/',
    },
  };
}

function getAdminSurfaceCopy(pathname: string, language: UiLanguage, isGuest: boolean): GateCopy {
  const isEnglish = language === 'en';

  if (pathname.startsWith('/admin/logs')) {
    return isGuest
      ? {
        eyebrow: isEnglish ? 'Admin Only' : '仅限管理员',
        statusLabel: isEnglish ? 'Admin Sign-in Required' : '需要管理员登录',
        title: isEnglish ? 'Sign in with an admin account to open logs center' : '请使用管理员账户登录后进入日志中心',
        description: isEnglish
          ? 'Execution logs remain in the operator surface and are not part of the guest or normal-user product flow.'
          : '执行日志仍属于 operator 控制面，不属于游客或普通用户的默认产品流。',
        bullets: isEnglish
          ? [
            'Guest mode never maps to bootstrap or admin identities.',
            'System logs stay protected even when the route is known.',
            'Use an admin account if you need provider, schedule, or observability control.',
          ]
          : [
            '游客模式绝不会映射到 bootstrap 或管理员身份。',
            '即使知道路由地址，系统日志仍然会被保护。',
            '如果你需要 provider、调度或可观测性控制，请使用管理员账户。',
          ],
        secondaryAction: {
          label: isEnglish ? 'Back home' : '返回首页',
          to: '/',
        },
      }
      : {
        eyebrow: isEnglish ? 'Admin Only' : '仅限管理员',
        statusLabel: isEnglish ? 'Admin Account Required' : '需要管理员账户',
        title: isEnglish ? 'This logs route requires an admin account' : '这个日志页面需要管理员账户',
        description: isEnglish
          ? 'Your current account can keep using the standard user product surface, but logs center stays reserved for operator workflows.'
          : '你当前账户仍可继续使用普通用户产品面，但日志中心保留给 operator 工作流。',
        bullets: isEnglish
          ? [
            'Normal users no longer see raw system observability surfaces in the default nav.',
            'If you expected access, sign out and re-enter with an admin account.',
            'Personal preferences remain available from the user settings surface.',
          ]
          : [
            '普通用户不会再在默认导航里看到原始系统可观测性界面。',
            '如果你本应拥有权限，请先退出当前账户，再使用管理员账户重新进入。',
            '你的个人偏好仍然可以在个人设置页面继续使用。',
          ],
        note: isEnglish
          ? 'Need the normal product instead? Personal settings remain the correct next stop.'
          : '如果你要继续正常产品流，个人设置仍然是更正确的下一站。',
        secondaryAction: {
          label: isEnglish ? 'Back home' : '返回首页',
          to: '/',
        },
      };
  }

  return isGuest
    ? {
      eyebrow: isEnglish ? 'Admin Only' : '仅限管理员',
      statusLabel: isEnglish ? 'Admin Sign-in Required' : '需要管理员登录',
      title: isEnglish ? 'Sign in with an admin account to enter operator surfaces' : '请使用管理员账户登录后进入 operator 界面',
      description: isEnglish
        ? 'System configuration, provider controls, schedules, channels, and operator logs are not part of the standard user product surface.'
        : '系统配置、provider 控制、调度、通道和 operator 日志不属于标准用户产品面。',
      bullets: isEnglish
        ? [
          'Guest mode never maps to admin or bootstrap identities.',
          'Operator controls stay behind explicit admin-only entry points.',
          'Use an admin account if you need system configuration rather than personal settings.',
        ]
        : [
          '游客模式绝不会映射到 admin 或 bootstrap 身份。',
          'operator 控制项仍然保留在显式的 admin-only 入口之后。',
          '如果你需要系统配置而不是个人偏好，请使用管理员账户登录。',
        ],
      secondaryAction: {
        label: isEnglish ? 'Back home' : '返回首页',
        to: '/',
      },
    }
    : {
      eyebrow: isEnglish ? 'Admin Only' : '仅限管理员',
      statusLabel: isEnglish ? 'Admin Account Required' : '需要管理员账户',
      title: isEnglish ? 'This operator surface requires an admin account' : '这个 operator 页面需要管理员账户',
      description: isEnglish
        ? 'System configuration, provider controls, schedules, channels, and operator logs remain outside the normal-user product surface.'
        : '系统配置、provider 控制、调度、通道和 operator 日志仍然留在普通用户产品面之外。',
      bullets: isEnglish
        ? [
          'Normal users no longer see raw system controls in the default navigation.',
          'If you expected access, sign out and re-enter with an admin account.',
          'Personal preferences remain available from the standard settings surface.',
        ]
        : [
          '普通用户不会再在默认导航里看到原始系统控制项。',
          '如果你本应拥有权限，请先退出当前账户，再使用管理员账户重新进入。',
          '个人偏好仍然保留在标准设置页面。',
        ],
      note: isEnglish
        ? 'Need user-facing tools instead? Open personal settings or return to the main workspace.'
        : '如果你要继续用户侧工具，请打开个人设置或返回主工作区。',
      secondaryAction: {
        label: isEnglish ? 'Back home' : '返回首页',
        to: '/',
      },
    };
}

export const RegisteredSurfaceRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const location = useLocation();
  const { language } = useI18n();
  const { isGuest } = useProductSurface();
  const gateCopy = getRegisteredSurfaceCopy(location.pathname, location.pathname + location.search, language);

  if (!isGuest) {
    return <>{children}</>;
  }

  return (
    <AccessGatePage
      eyebrow={gateCopy.eyebrow}
      title={gateCopy.title}
      description={gateCopy.description}
      bullets={gateCopy.bullets}
      statusLabel={gateCopy.statusLabel}
      note={gateCopy.note}
      primaryAction={{
        label: language === 'en' ? 'Sign in now' : '立即登录',
        to: buildLoginPath(location.pathname + location.search),
      }}
      secondaryAction={gateCopy.secondaryAction}
      tertiaryAction={gateCopy.tertiaryAction}
    />
  );
};

export const AdminSurfaceRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const location = useLocation();
  const { language } = useI18n();
  const { isAdmin, isAdminMode, isGuest } = useProductSurface();
  const gateCopy = getAdminSurfaceCopy(location.pathname, language, isGuest);

  if (isAdmin && isAdminMode) {
    return <>{children}</>;
  }

  if (isAdmin && !isAdminMode) {
    return (
      <AccessGatePage
        eyebrow={language === 'en' ? 'Admin Mode Required' : '需要 Admin Mode'}
        title={language === 'en' ? 'Turn on Admin Mode to open operator tools' : '请先开启 Admin Mode 再进入 operator 工具'}
        description={language === 'en'
          ? 'Your admin account is currently using the safer User Mode surface. Enable Admin Mode explicitly before entering system settings or logs.'
          : '你的管理员账户当前仍停留在更安全的 User Mode 产品面。请显式开启 Admin Mode 后，再进入系统设置或日志中心。'}
        bullets={language === 'en'
          ? [
            'Admin accounts now default to the same user-like surface used for everyday analysis.',
            'Operator pages stay hidden until Admin Mode is intentionally enabled.',
            'Use the header switch or personal settings page to enter Admin Mode, then retry this route.',
          ]
          : [
            '管理员账户现在会默认先进入普通用户式的日常分析产品面。',
            'operator 页面会保持隐藏，直到你显式开启 Admin Mode。',
            '请通过顶部切换按钮或个人设置页进入 Admin Mode，然后再重试当前路由。',
          ]}
        statusLabel={language === 'en' ? 'User Mode Active' : '当前仍为 User Mode'}
        note={language === 'en'
          ? 'Need normal tools instead? Personal settings remain available without leaving User Mode.'
          : '如果你只是继续普通工具流，个人设置页仍然可以在 User Mode 中直接使用。'}
        primaryAction={{
          label: language === 'en' ? 'Open personal settings' : '打开个人设置',
          to: '/settings',
        }}
        secondaryAction={{
          label: language === 'en' ? 'Back home' : '返回首页',
          to: '/',
        }}
      />
    );
  }

  return (
    <AccessGatePage
      eyebrow={gateCopy.eyebrow}
      title={gateCopy.title}
      description={gateCopy.description}
      bullets={gateCopy.bullets}
      statusLabel={gateCopy.statusLabel}
      note={gateCopy.note}
      primaryAction={{
        label: isGuest ? (language === 'en' ? 'Sign in' : '登录') : (language === 'en' ? 'Open personal settings' : '打开个人设置'),
        to: isGuest ? buildLoginPath(location.pathname + location.search) : '/settings',
      }}
      secondaryAction={gateCopy.secondaryAction}
    />
  );
};

export const AppContent: React.FC = () => {
  const location = useLocation();
  const { authEnabled, loggedIn, isLoading, loadError, refreshStatus } = useAuth();
  const { t } = useI18n();
  const bootStartedAt = useRef<number>(0);
  const [showBootSplash, setShowBootSplash] = useState(true);
  const [bootSplashFading, setBootSplashFading] = useState(false);
  const splashDismissed = useRef(false);

  useEffect(() => {
    useAgentChatStore.getState().setCurrentRoute(location.pathname);
  }, [location.pathname]);

  useEffect(() => {
    if (bootStartedAt.current === 0) {
      bootStartedAt.current = Date.now();
    }
  }, []);

  useEffect(() => {
    if (isLoading || splashDismissed.current) {
      return;
    }

    if (bootStartedAt.current === 0) {
      bootStartedAt.current = Date.now();
    }
    const elapsed = Date.now() - bootStartedAt.current;
    const waitMs = Math.max(0, APP_BOOT_SPLASH_MIN_MS - elapsed);
    let hideTimer: number | undefined;
    const fadeTimer = window.setTimeout(() => {
      splashDismissed.current = true;
      setBootSplashFading(true);
      hideTimer = window.setTimeout(() => {
        setShowBootSplash(false);
      }, APP_BOOT_SPLASH_FADE_MS);
    }, waitMs);

    return () => {
      window.clearTimeout(fadeTimer);
      if (hideTimer !== undefined) {
        window.clearTimeout(hideTimer);
      }
    };
  }, [isLoading]);

  let content: React.ReactNode = null;

  if (loadError) {
    content = (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-base px-4">
        <div className="theme-panel-glass w-full max-w-xl px-5 py-5">
          <ApiErrorAlert error={loadError} />
          <div className="mt-4 flex justify-end">
            <button
              type="button"
              className="btn-primary"
              onClick={() => void refreshStatus()}
            >
              {t('app.retry')}
            </button>
          </div>
        </div>
      </div>
    );
  } else if (!isLoading) {
    if (location.pathname === '/login') {
      const redirectTarget = resolveAuthRedirect(location.search, '/');
      if (!authEnabled || loggedIn) {
        content = <Navigate to={redirectTarget} replace />;
      } else {
        content = <LoginPage />;
      }
    } else {
      content = (
        <Routes>
          <Route element={<Shell />}>
            <Route path="/" element={<HomeSurfacePage />} />
            <Route path="/scanner" element={<ScannerSurfacePage />} />
            <Route path="/chat" element={<RegisteredSurfaceRoute><ChatPage /></RegisteredSurfaceRoute>} />
            <Route path="/portfolio" element={<RegisteredSurfaceRoute><PortfolioPage /></RegisteredSurfaceRoute>} />
            <Route path="/backtest" element={<RegisteredSurfaceRoute><BacktestPage /></RegisteredSurfaceRoute>} />
            <Route path="/backtest/results/:runId" element={<RegisteredSurfaceRoute><DeterministicBacktestResultPage /></RegisteredSurfaceRoute>} />
            <Route path="/settings" element={<PersonalSettingsPage />} />
            <Route path="/settings/system" element={<AdminSurfaceRoute><SettingsPage /></AdminSurfaceRoute>} />
            <Route path="/admin/logs" element={<AdminSurfaceRoute><AdminLogsPage /></AdminSurfaceRoute>} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
          <Route path="/login" element={<LoginPage />} />
        </Routes>
      );
    }
  }

  return (
    <>
      {content}
      {showBootSplash ? (
        <BrandedLoadingScreen
          fading={bootSplashFading}
          text={t('app.loadingBrand')}
          subtext={isLoading ? t('app.loading') : undefined}
        />
      ) : null}
    </>
  );
};

const PreviewRoutes: React.FC = () => (
  <PreviewShell>
    <Routes>
      <Route path="/__preview/report" element={<PreviewReportPage />} />
      <Route path="/__preview/full-report" element={<PreviewFullReportDrawerPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  </PreviewShell>
);

const AppBody: React.FC = () => {
  const location = useLocation();
  const isPreviewRoute = import.meta.env.DEV && location.pathname.startsWith('/__preview/');

  if (isPreviewRoute) {
    return <PreviewRoutes />;
  }

  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
};

const App: React.FC = () => {
  useEffect(() => {
    const staticSplash = document.getElementById(STATIC_BOOT_SPLASH_ID);
    if (!staticSplash) {
      return;
    }
    staticSplash.classList.add('is-fading');
    const timer = window.setTimeout(() => {
      staticSplash.remove();
    }, APP_BOOT_SPLASH_FADE_MS);
    return () => {
      window.clearTimeout(timer);
    };
  }, []);

  return (
    <Router>
      <AppBody />
    </Router>
  );
};

export default App;
