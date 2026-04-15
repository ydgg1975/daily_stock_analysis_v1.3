import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '../../theme/ThemeProvider';
import { Shell } from '../Shell';
import { setAdminSurfaceMode } from '../../../hooks/useProductSurface';
import { useShellRailSlot } from '../useShellRailSlot';

const { mockLogout, mockGetAgentStatus, useAuthMock } = vi.hoisted(() => ({
  mockLogout: vi.fn().mockResolvedValue(undefined),
  mockGetAgentStatus: vi.fn().mockResolvedValue({ enabled: true }),
  useAuthMock: vi.fn(),
}));

vi.mock('../../../contexts/AuthContext', () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock('../../../stores/agentChatStore', () => ({
  useAgentChatStore: (selector: (state: { completionBadge: boolean }) => unknown) =>
    selector({ completionBadge: true }),
}));

vi.mock('../../../api/agent', () => ({
  agentApi: {
    getStatus: (...args: unknown[]) => mockGetAgentStatus(...args),
  },
}));

beforeAll(() => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: query === '(prefers-color-scheme: dark)',
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
});

afterEach(() => {
  window.innerWidth = 1024;
  window.dispatchEvent(new Event('resize'));
});

const ShellRailFixture = () => {
  useShellRailSlot(<div>archive content</div>);
  return <div>page content</div>;
};

const LocationProbe = () => {
  const location = useLocation();
  return <div data-testid="location-path">{location.pathname}</div>;
};

const settleDrawerMotion = () => new Promise((resolve) => window.setTimeout(resolve, 260));
const settleDrawerStability = () => new Promise((resolve) => window.setTimeout(resolve, 480));

describe('Shell', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setAdminSurfaceMode('user');
    window.sessionStorage.clear();
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: true,
      currentUser: { isAdmin: false },
      logout: mockLogout,
    });
  });

  it('renders the streamlined navigation and completion badge without the old theme control', () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    expect(screen.queryByRole('button', { name: '切换主题' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'WolfyStock' })).toHaveAttribute('href', '/');
    expect(screen.getByRole('link', { name: '问股' })).toBeInTheDocument();
    expect(screen.getByTestId('chat-completion-badge')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '退出' })).toBeInTheDocument();
  });

  it('shows a guest-safe navigation set when the visitor is not signed in', () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: false,
      currentUser: null,
      logout: mockLogout,
    });

    render(
      <MemoryRouter initialEntries={['/']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    expect(screen.getByRole('link', { name: '首页' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '扫描器' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '设置' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '登录' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: '问股' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: '持仓' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: '回测' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '退出' })).not.toBeInTheDocument();
  });

  it('hides the Ask Stock navigation entry when the agent runtime is unavailable', async () => {
    mockGetAgentStatus.mockResolvedValueOnce({ enabled: false });

    render(
      <MemoryRouter initialEntries={['/']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.queryByRole('link', { name: '问股' })).not.toBeInTheDocument();
    });
  });

  it('shows a confirmation dialog before logout', async () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ThemeProvider>
          <Shell>
            <LocationProbe />
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole('button', { name: '退出' }));

    expect(await screen.findByRole('heading', { name: '退出登录' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '确认退出' }));

    await waitFor(() => expect(mockLogout).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByTestId('location-path')).toHaveTextContent('/'));
  });

  it('keeps language/logout controls inside the mobile drawer instead of duplicating them in the top bar', async () => {
    window.innerWidth = 375;

    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    expect(screen.queryByRole('button', { name: '切换主题' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '切换语言' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '打开导航菜单' }));

    expect(await screen.findByRole('button', { name: '切换语言' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '退出' })).toBeInTheDocument();
  });

  it('keeps the mobile navigation drawer open until the user closes it or navigates away', async () => {
    window.innerWidth = 375;

    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole('button', { name: '打开导航菜单' }));
    expect(await screen.findByRole('heading', { name: '导航菜单' })).toBeInTheDocument();

    await act(async () => {
      await settleDrawerStability();
    });

    expect(screen.getByRole('heading', { name: '导航菜单' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '切换语言' })).toBeInTheDocument();
  });

  it('adds a dedicated content-frame modifier for the backtest route', () => {
    render(
      <MemoryRouter initialEntries={['/backtest']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    expect(document.querySelector('.shell-content-frame--backtest')).not.toBeNull();
  });

  it('keeps admin accounts in User Mode by default and only shows system entry after switching modes', async () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      loggedIn: true,
      currentUser: { isAdmin: true },
      logout: mockLogout,
    });

    render(
      <MemoryRouter initialEntries={['/settings']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    expect(screen.queryByRole('link', { name: '系统设置' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '进入 Admin Mode' }));
    expect(await screen.findByRole('link', { name: '系统设置' })).toHaveAttribute('href', '/settings/system');
    fireEvent.click(screen.getByRole('button', { name: '返回 User Mode' }));
    await waitFor(() => {
      expect(screen.queryByRole('link', { name: '系统设置' })).not.toBeInTheDocument();
    });
  });

  it('resets mobile drawer and archive rail state when crossing back to desktop', async () => {
    window.innerWidth = 390;

    render(
      <MemoryRouter initialEntries={['/']}>
        <ThemeProvider>
          <Shell>
            <ShellRailFixture />
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '打开导航菜单' }));
      await settleDrawerMotion();
    });
    expect(await screen.findByRole('heading', { name: '导航菜单' })).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(screen.getAllByRole('button', { name: '分析档案' })[0]);
      await settleDrawerMotion();
    });
    await waitFor(() => {
      expect(screen.getAllByRole('dialog')).toHaveLength(1);
    });
    expect(document.body.style.overflow).toBe('hidden');

    window.innerWidth = 1280;
    await act(async () => {
      fireEvent(window, new Event('resize'));
      await settleDrawerMotion();
    });

    await waitFor(() => {
      expect(screen.queryAllByRole('dialog')).toHaveLength(0);
    });
    expect(document.body.style.overflow).toBe('');

    window.innerWidth = 390;
    await act(async () => {
      fireEvent(window, new Event('resize'));
      await settleDrawerMotion();
    });

    await waitFor(() => {
      expect(screen.queryAllByRole('dialog')).toHaveLength(0);
    });
    expect(screen.getByRole('button', { name: '打开导航菜单' })).toBeInTheDocument();
  });
});
