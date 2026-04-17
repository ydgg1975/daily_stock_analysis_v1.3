import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AppContent } from '../App';

const { useAuthMock, useProductSurfaceMock, setCurrentRouteMock, setLanguageMock } = vi.hoisted(() => ({
  useAuthMock: vi.fn(),
  useProductSurfaceMock: vi.fn(),
  setCurrentRouteMock: vi.fn(),
  setLanguageMock: vi.fn(),
}));

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock('../hooks/useProductSurface', () => ({
  buildLoginPath: (path: string) => `/login?redirect=${encodeURIComponent(path)}`,
  buildRegistrationPath: (path: string) => `/login?mode=create&redirect=${encodeURIComponent(path)}`,
  resolveAuthRedirect: (search: string, fallback = '/') => new URLSearchParams(search).get('redirect') || fallback,
  useProductSurface: () => useProductSurfaceMock(),
}));

vi.mock('../contexts/UiLanguageContext', () => ({
  useI18n: () => ({
    language: 'en',
    setLanguage: setLanguageMock,
    t: (key: string) => key,
  }),
}));

vi.mock('../stores/agentChatStore', () => ({
  useAgentChatStore: Object.assign(
    (selector?: (state: Record<string, unknown>) => unknown) => (selector ? selector({}) : {}),
    { getState: () => ({ setCurrentRoute: setCurrentRouteMock }) },
  ),
}));

vi.mock('../components/common', async () => {
  const React = await vi.importActual<typeof import('react')>('react');
  const actual = await vi.importActual<typeof import('../components/common')>('../components/common');
  const router = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    Shell: () => React.createElement('div', { 'data-testid': 'shell-frame' }, React.createElement(router.Outlet)),
    BrandedLoadingScreen: () => null,
    ApiErrorAlert: () => React.createElement('div', {}, 'api-error'),
  };
});

vi.mock('../pages/HomeSurfacePage', () => ({
  default: () => <div>home-surface-page</div>,
}));

vi.mock('../pages/ScannerSurfacePage', () => ({
  default: () => <div>scanner-surface-page</div>,
}));

vi.mock('../pages/ChatPage', () => ({
  default: () => <div>chat-page</div>,
}));

vi.mock('../pages/PortfolioPage', () => ({
  default: () => <div>portfolio-page</div>,
}));

vi.mock('../pages/BacktestPage', () => ({
  default: () => <div>backtest-page</div>,
}));

vi.mock('../pages/DeterministicBacktestResultPage', () => ({
  default: () => <div>backtest-result-page</div>,
}));

vi.mock('../pages/PersonalSettingsPage', () => ({
  default: () => <div>personal-settings-page</div>,
}));

vi.mock('../pages/SettingsPage', () => ({
  default: () => <div>system-settings-page</div>,
}));

vi.mock('../pages/AdminLogsPage', () => ({
  default: () => <div>admin-logs-page</div>,
}));

vi.mock('../pages/LoginPage', () => ({
  default: () => <div>login-page</div>,
}));

vi.mock('../pages/NotFoundPage', () => ({
  default: () => <div>not-found-page</div>,
}));

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppContent />
    </MemoryRouter>,
  );
}

describe('AppContent route flows', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: false,
      isLoading: false,
      loadError: null,
      refreshStatus: vi.fn(),
    });
    useProductSurfaceMock.mockReturnValue({
      isGuest: true,
      isAdmin: false,
      isAdminMode: false,
    });
  });

  it('renders the guest homepage on the root route', async () => {
    renderAt('/');
    expect(await screen.findByText('home-surface-page')).toBeInTheDocument();
  });

  it('gates guest access to registered-user routes with a redirect-aware sign-in link', async () => {
    renderAt('/chat');
    expect(await screen.findByRole('heading', { name: 'Sign in to continue Ask Stock follow-up' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Sign in now' })).toHaveAttribute('href', '/login?redirect=%2Fchat');
  });

  it('redirects away from login to the requested route after authentication succeeds', async () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: true,
      isLoading: false,
      loadError: null,
      refreshStatus: vi.fn(),
    });
    useProductSurfaceMock.mockReturnValue({
      isGuest: false,
      isAdmin: false,
      isAdminMode: false,
    });

    renderAt('/login?redirect=%2Fportfolio');

    expect(await screen.findByText('portfolio-page')).toBeInTheDocument();
    expect(screen.queryByText('login-page')).not.toBeInTheDocument();
  });

  it('shows the admin-account gate when a normal user visits an admin route', async () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: true,
      isLoading: false,
      loadError: null,
      refreshStatus: vi.fn(),
    });
    useProductSurfaceMock.mockReturnValue({
      isGuest: false,
      isAdmin: false,
      isAdminMode: false,
    });

    renderAt('/settings/system');

    expect(await screen.findByRole('heading', { name: 'This operator surface requires an admin account' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open personal settings' })).toHaveAttribute('href', '/settings');
  });

  it('shows the admin-mode gate when an admin account stays in User Mode', async () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: true,
      isLoading: false,
      loadError: null,
      refreshStatus: vi.fn(),
    });
    useProductSurfaceMock.mockReturnValue({
      isGuest: false,
      isAdmin: true,
      isAdminMode: false,
    });

    renderAt('/settings/system');

    expect(await screen.findByRole('heading', { name: 'Turn on Admin Mode to open operator tools' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open personal settings' })).toHaveAttribute('href', '/settings');
  });

  it('renders admin routes once Admin Mode is enabled', async () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: true,
      isLoading: false,
      loadError: null,
      refreshStatus: vi.fn(),
    });
    useProductSurfaceMock.mockReturnValue({
      isGuest: false,
      isAdmin: true,
      isAdminMode: true,
    });

    renderAt('/settings/system');

    await waitFor(() => expect(screen.getByText('system-settings-page')).toBeInTheDocument());
  });

  it('supports locale-prefixed product routes and syncs language from the path', async () => {
    renderAt('/en/chat');

    expect(await screen.findByRole('heading', { name: 'Sign in to continue Ask Stock follow-up' })).toBeInTheDocument();
    expect(screen.getByText('Guest Preview Only')).toBeInTheDocument();
  });
});
