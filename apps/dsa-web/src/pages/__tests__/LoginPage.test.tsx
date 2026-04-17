import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import LoginPage from '../LoginPage';

const { navigate, useSearchParamsMock, useAuthMock } = vi.hoisted(() => ({
  navigate: vi.fn(),
  useSearchParamsMock: vi.fn(),
  useAuthMock: vi.fn(),
}));

vi.mock('../../hooks', () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigate,
    useSearchParams: () => useSearchParamsMock(),
  };
});

describe('LoginPage', () => {
  const renderPage = () => render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>,
  );

  beforeEach(() => {
    vi.clearAllMocks();
    useSearchParamsMock.mockReturnValue([new URLSearchParams('redirect=%2Fsettings')]);
  });

  it('blocks first-time setup when confirmation does not match', async () => {
    const login = vi.fn();
    useAuthMock.mockReturnValue({
      login,
      passwordSet: false,
      setupState: 'no_password',
    });

    renderPage();

    fireEvent.change(screen.getByLabelText('管理员密码'), { target: { value: 'passwd6' } });
    fireEvent.change(screen.getByLabelText('确认密码'), { target: { value: 'passwd7' } });
    fireEvent.click(screen.getByRole('button', { name: '完成设置并登录' }));

    expect(await screen.findByText('两次输入的密码不一致')).toBeInTheDocument();
    expect(login).not.toHaveBeenCalled();
  });

  it('navigates to redirect after a successful login', async () => {
    useAuthMock.mockReturnValue({
      login: vi.fn().mockResolvedValue({ success: true }),
      passwordSet: true,
      setupState: 'enabled',
    });

    renderPage();

    fireEvent.change(screen.getByLabelText('登录密码'), { target: { value: 'passwd6' } });
    fireEvent.click(screen.getByRole('button', { name: '授权进入工作台' }));

    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/settings', { replace: true }));
  });

  it('enters create-account mode directly when requested by the route and shows destination context', () => {
    useSearchParamsMock.mockReturnValue([new URLSearchParams('mode=create&redirect=%2Fscanner')]);
    useAuthMock.mockReturnValue({
      login: vi.fn(),
      passwordSet: true,
      setupState: 'enabled',
    });

    renderPage();

    expect(screen.getByRole('heading', { name: '创建账户并登录' })).toBeInTheDocument();
    expect(screen.getByLabelText('用户名')).toBeInTheDocument();
    expect(screen.getByLabelText('显示名称')).toBeInTheDocument();
    expect(screen.getByText('登录后将继续进入：扫描器工作区')).toBeInTheDocument();
  });

  it('offers a safe exit back to home for direct login entry', () => {
    useSearchParamsMock.mockReturnValue([new URLSearchParams('')]);
    useAuthMock.mockReturnValue({
      login: vi.fn(),
      passwordSet: true,
      setupState: 'enabled',
    });

    renderPage();

    fireEvent.click(screen.getByRole('button', { name: '返回首页' }));

    expect(navigate).toHaveBeenCalledWith('/', { replace: true });
  });

  it('offers a safe exit back to the public scanner surface when redirected from scanner', () => {
    useSearchParamsMock.mockReturnValue([new URLSearchParams('redirect=%2Fscanner')]);
    useAuthMock.mockReturnValue({
      login: vi.fn(),
      passwordSet: true,
      setupState: 'enabled',
    });

    renderPage();

    fireEvent.click(screen.getByRole('button', { name: '返回扫描器预览' }));

    expect(navigate).toHaveBeenCalledWith('/scanner', { replace: true });
  });

  it('keeps locale-prefixed exit targets when redirected from a localized route', () => {
    window.history.replaceState(window.history.state, '', '/en/login?redirect=%2Fen%2Fscanner');
    useSearchParamsMock.mockReturnValue([new URLSearchParams('redirect=%2Fen%2Fscanner')]);
    useAuthMock.mockReturnValue({
      login: vi.fn(),
      passwordSet: true,
      setupState: 'enabled',
    });

    renderPage();

    fireEvent.click(screen.getByRole('button', { name: '返回扫描器预览' }));

    expect(navigate).toHaveBeenCalledWith('/en/scanner', { replace: true });
  });
});
