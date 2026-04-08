import type React from 'react';
import { useEffect, useRef, useState } from 'react';
import { BrowserRouter as Router, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import HomePage from './pages/HomePage';
import BacktestPage from './pages/BacktestPage';
import SettingsPage from './pages/SettingsPage';
import LoginPage from './pages/LoginPage';
import NotFoundPage from './pages/NotFoundPage';
import ChatPage from './pages/ChatPage';
import PortfolioPage from './pages/PortfolioPage';
import PreviewReportPage from './pages/PreviewReportPage';
import PreviewFullReportDrawerPage from './pages/PreviewFullReportDrawerPage';
import AdminLogsPage from './pages/AdminLogsPage';
import { ApiErrorAlert, BrandedLoadingScreen, Shell } from './components/common';
import { PreviewShell } from './components/layout/PreviewShell';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { useI18n } from './contexts/UiLanguageContext';
import { useAgentChatStore } from './stores/agentChatStore';

const APP_BOOT_SPLASH_MIN_MS = 950;
const APP_BOOT_SPLASH_FADE_MS = 380;
const STATIC_BOOT_SPLASH_ID = 'boot-splash';

const AppContent: React.FC = () => {
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
  } else if (!isLoading && authEnabled && !loggedIn) {
    if (location.pathname === '/login') {
      content = <LoginPage />;
    } else {
      const redirect = encodeURIComponent(location.pathname + location.search);
      content = <Navigate to={`/login?redirect=${redirect}`} replace />;
    }
  } else if (!isLoading) {
    if (location.pathname === '/login') {
      content = <Navigate to="/" replace />;
    } else {
      content = (
        <Routes>
          <Route element={<Shell />}>
            <Route path="/" element={<HomePage />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/portfolio" element={<PortfolioPage />} />
            <Route path="/backtest" element={<BacktestPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/admin/logs" element={<AdminLogsPage />} />
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
