import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '../../theme/ThemeProvider';
import { Shell } from '../Shell';

const mockLogout = vi.fn().mockResolvedValue(undefined);

vi.mock('../../../contexts/AuthContext', () => ({
  useAuth: () => ({
    authEnabled: true,
    logout: mockLogout,
  }),
}));

vi.mock('../../../stores/agentChatStore', () => ({
  useAgentChatStore: (selector: (state: { completionBadge: boolean }) => unknown) =>
    selector({ completionBadge: true }),
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

describe('Shell', () => {
  it('renders navigation, theme toggle and completion badge', () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    expect(screen.getAllByRole('button', { name: '切换主题' }).length).toBeGreaterThan(0);
    expect(screen.getByRole('link', { name: '问股' })).toBeInTheDocument();
    expect(screen.getByTestId('chat-completion-badge')).toBeInTheDocument();
    const logoutButton = screen.getByRole('button', { name: '退出' });
    expect(logoutButton).toBeInTheDocument();
    expect(logoutButton).toHaveClass('cursor-pointer');
  });

  it('opens the theme menu from the sidebar toggle', async () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    fireEvent.click(screen.getAllByRole('button', { name: '切换主题' })[0]);

    expect(await screen.findByRole('menu', { name: '主题模式' })).toBeInTheDocument();
  });

  it('shows a confirmation dialog before logout', async () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <ThemeProvider>
          <Shell>
            <div>page content</div>
          </Shell>
        </ThemeProvider>
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole('button', { name: '退出' }));

    expect(await screen.findByRole('heading', { name: '退出登录' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '确认退出' }));
    expect(mockLogout).toHaveBeenCalled();
  });

  it('keeps theme and language controls inside the mobile drawer instead of duplicating them in the top bar', async () => {
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

    expect(await screen.findByRole('button', { name: '切换主题' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '切换语言' })).toBeInTheDocument();
  });
});
