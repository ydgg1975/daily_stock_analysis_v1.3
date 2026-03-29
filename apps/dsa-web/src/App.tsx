import type React from 'react';
import { useEffect } from 'react';
import { BrowserRouter as Router, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import HomePage from './pages/HomePage';
import BacktestPage from './pages/BacktestPage';
import SettingsPage from './pages/SettingsPage';
import LoginPage from './pages/LoginPage';
import NotFoundPage from './pages/NotFoundPage';
import ChatPage from './pages/ChatPage';
import PortfolioPage from './pages/PortfolioPage';
import PreviewReportPage from './pages/PreviewReportPage';
import { ApiErrorAlert, Shell } from './components/common';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { useAgentChatStore } from './stores/agentChatStore';
import { ThemeToggle } from './components/theme/ThemeToggle';
import './App.css';

const AppContent: React.FC = () => {
  const location = useLocation();
  const { authEnabled, loggedIn, isLoading, loadError, refreshStatus } = useAuth();

  useEffect(() => {
    useAgentChatStore.getState().setCurrentRoute(location.pathname);
  }, [location.pathname]);

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-base">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-cyan/20 border-t-cyan" />
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-base px-4">
        <div className="w-full max-w-lg">
          <ApiErrorAlert error={loadError} />
        </div>
        <button
          type="button"
          className="btn-primary"
          onClick={() => void refreshStatus()}
        >
          重试
        </button>
      </div>
    );
  }

  if (authEnabled && !loggedIn) {
    if (location.pathname === '/login') {
      return <LoginPage />;
    }
    const redirect = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?redirect=${redirect}`} replace />;
  }

  if (location.pathname === '/login') {
    return <Navigate to="/" replace />;
  }

  return (
    <Routes>
      <Route element={<Shell />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/portfolio" element={<PortfolioPage />} />
        <Route path="/backtest" element={<BacktestPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
      <Route path="/login" element={<LoginPage />} />
    </Routes>
  );
};

const PreviewAppShell: React.FC = () => (
  <div className="theme-shell dark min-h-screen overflow-x-clip text-foreground">
    <div className="pointer-events-none fixed right-3 top-3 z-40">
      <div className="pointer-events-auto">
        <ThemeToggle />
      </div>
    </div>

    <div className="mx-auto flex min-h-screen w-full max-w-[var(--layout-shell-max)] gap-[var(--layout-gap)] px-2 py-2 sm:px-3 sm:py-3 lg:px-4">
      <aside className="theme-sidebar-shell sticky top-3 hidden max-h-[calc(100vh-1.5rem)] w-[var(--layout-sidebar-width)] shrink-0 self-start overflow-hidden rounded-[1.6rem] p-2.5 lg:flex">
        <div className="flex h-full min-h-0 w-full flex-col gap-4">
          <div className="theme-sidebar-brand flex items-center justify-between rounded-[1rem] px-4 py-3">
            <div>
              <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">Preview Shell</p>
              <p className="mt-1 text-sm font-semibold text-foreground">Responsive report</p>
            </div>
            <div className="hidden xl:block">
              <ThemeToggle />
            </div>
          </div>
          <div className="theme-panel-subtle rounded-[1rem] px-4 py-4">
            <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">Desktop rail</p>
            <p className="mt-2 text-sm leading-6 text-secondary-text">
              这个开发态壳层复用了正式环境的 workspace 宽度、侧栏宽度和内容起点，用于校验桌面/移动断点下的真实节奏。
            </p>
          </div>
        </div>
      </aside>

      <main className="min-h-0 min-w-0 flex-1 pt-14 lg:pt-0">
        <Routes>
          <Route path="/__preview/report" element={<PreviewReportPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>
    </div>
  </div>
);

const AppBody: React.FC = () => {
  const location = useLocation();
  const isPreviewRoute = import.meta.env.DEV && location.pathname.startsWith('/__preview/');

  if (isPreviewRoute) {
    return <PreviewAppShell />;
  }

  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
};

const App: React.FC = () => {
  return (
    <Router>
      <AppBody />
    </Router>
  );
};

export default App;
