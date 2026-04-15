import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PersonalSettingsPage from '../PersonalSettingsPage';

const {
  getNotificationPreferences,
  updateNotificationPreferences,
  setLanguage,
  setMarketColorConvention,
  setAdminSurfaceModeMock,
  useAuthMock,
  useProductSurfaceMock,
} = vi.hoisted(() => ({
  getNotificationPreferences: vi.fn(),
  updateNotificationPreferences: vi.fn(),
  setLanguage: vi.fn(),
  setMarketColorConvention: vi.fn(),
  setAdminSurfaceModeMock: vi.fn(),
  useAuthMock: vi.fn(),
  useProductSurfaceMock: vi.fn(),
}));

vi.mock('../../contexts/UiLanguageContext', () => ({
  useI18n: () => ({
    language: 'zh',
    setLanguage,
    t: (key: string) => ({
      'settings.languageTitle': '语言',
      'settings.languageDesc': '切换界面语言',
      'settings.marketColorTitle': '涨跌颜色',
      'settings.marketColorDesc': '选择价格涨跌颜色约定',
      'settings.marketColorConventional': '国际惯例',
      'settings.marketColorConventionalDesc': '红跌绿涨',
      'settings.marketColorCn': 'A 股惯例',
      'settings.marketColorCnDesc': '红涨绿跌',
      'language.zh': '中文',
      'language.en': 'EN',
    }[key] || key),
  }),
}));

vi.mock('../../contexts/UiPreferencesContext', () => ({
  useUiPreferences: () => ({
    marketColorConvention: 'redDownGreenUp',
    setMarketColorConvention,
  }),
}));

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock('../../api/auth', () => ({
  authApi: {
    getNotificationPreferences,
    updateNotificationPreferences,
  },
}));

vi.mock('../../hooks/useProductSurface', () => ({
  buildLoginPath: (path: string) => `/login?redirect=${encodeURIComponent(path)}`,
  buildRegistrationPath: (path: string) => `/login?mode=create&redirect=${encodeURIComponent(path)}`,
  useProductSurface: () => useProductSurfaceMock(),
}));

vi.mock('../../components/settings/FontSizeSettingsCard', () => ({
  FontSizeSettingsCard: () => <div>font-size-card</div>,
}));

vi.mock('../../components/settings/ChangePasswordCard', () => ({
  ChangePasswordCard: () => <div>change-password-card</div>,
}));

describe('PersonalSettingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getNotificationPreferences.mockResolvedValue({
      channel: 'email',
      enabled: false,
      email: null,
      emailEnabled: false,
      discordEnabled: false,
      discordWebhook: null,
      deliveryAvailable: true,
      emailDeliveryAvailable: true,
      discordDeliveryAvailable: true,
      updatedAt: null,
    });
    updateNotificationPreferences.mockResolvedValue({
      channel: 'email',
      enabled: false,
      email: null,
      emailEnabled: false,
      discordEnabled: false,
      discordWebhook: null,
      deliveryAvailable: true,
      emailDeliveryAvailable: true,
      discordDeliveryAvailable: true,
      updatedAt: null,
    });
  });

  it('shows guest-only sign-in guidance without system links', () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      passwordChangeable: false,
    });
    useProductSurfaceMock.mockReturnValue({
      isGuest: true,
      isAdmin: false,
      isAdminMode: false,
      loggedIn: false,
      currentUser: null,
      setAdminSurfaceMode: setAdminSurfaceModeMock,
    });

    render(
      <MemoryRouter>
        <PersonalSettingsPage />
      </MemoryRouter>,
    );

    expect(screen.getByText('当前仅为游客偏好')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '登录后解锁个人数据' })).toHaveAttribute('href', '/login?redirect=%2Fsettings');
    expect(screen.getByRole('link', { name: '创建账户' })).toHaveAttribute('href', '/login?mode=create&redirect=%2Fsettings');
    expect(screen.queryByText('Operator 入口')).not.toBeInTheDocument();
    expect(getNotificationPreferences).not.toHaveBeenCalled();
  });

  it('keeps admins in User Mode by default and hides operator links until Admin Mode is enabled', async () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      passwordChangeable: true,
    });
    useProductSurfaceMock.mockReturnValue({
      isGuest: false,
      isAdmin: true,
      isAdminMode: false,
      loggedIn: true,
      currentUser: {
        username: 'admin',
        displayName: 'Admin',
      },
      setAdminSurfaceMode: setAdminSurfaceModeMock,
    });
    getNotificationPreferences.mockResolvedValue({
      channel: 'email',
      enabled: true,
      email: 'admin@example.com',
      emailEnabled: true,
      discordEnabled: true,
      discordWebhook: 'https://discord.com/api/webhooks/123/token',
      deliveryAvailable: true,
      emailDeliveryAvailable: true,
      discordDeliveryAvailable: true,
      updatedAt: '2026-04-15T09:00:00Z',
    });

    render(
      <MemoryRouter>
        <PersonalSettingsPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(getNotificationPreferences).toHaveBeenCalledTimes(1));
    expect(screen.getByText('Admin 模式分层')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '进入 Admin Mode' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: '进入系统设置' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: '查看管理员日志' })).not.toBeInTheDocument();
    expect(screen.getByDisplayValue('admin@example.com')).toBeInTheDocument();
    expect(screen.getByDisplayValue('https://discord.com/api/webhooks/123/token')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '保存通知目标' })).toBeInTheDocument();
    expect(screen.getByText('change-password-card')).toBeInTheDocument();
    expect(screen.getByText('font-size-card')).toBeInTheDocument();
  });

  it('shows operator entry points after Admin Mode is enabled', async () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      passwordChangeable: false,
    });
    useProductSurfaceMock.mockReturnValue({
      isGuest: false,
      isAdmin: true,
      isAdminMode: true,
      loggedIn: true,
      currentUser: {
        username: 'admin',
        displayName: 'Admin',
      },
      setAdminSurfaceMode: setAdminSurfaceModeMock,
    });

    render(
      <MemoryRouter>
        <PersonalSettingsPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(getNotificationPreferences).toHaveBeenCalledTimes(1));
    expect(screen.getByRole('link', { name: '进入系统设置' })).toHaveAttribute('href', '/settings/system');
    expect(screen.getByRole('link', { name: '查看管理员日志' })).toHaveAttribute('href', '/admin/logs');
    expect(screen.getByRole('button', { name: '返回 User Mode' })).toBeInTheDocument();
  });

  it('saves email and Discord notification targets together for signed-in users', async () => {
    useAuthMock.mockReturnValue({
      authEnabled: true,
      passwordChangeable: false,
    });
    useProductSurfaceMock.mockReturnValue({
      isGuest: false,
      isAdmin: false,
      isAdminMode: false,
      loggedIn: true,
      currentUser: {
        username: 'alice',
        displayName: 'Alice',
      },
      setAdminSurfaceMode: setAdminSurfaceModeMock,
    });
    getNotificationPreferences.mockResolvedValue({
      channel: 'email',
      enabled: false,
      email: null,
      emailEnabled: false,
      discordEnabled: false,
      discordWebhook: null,
      deliveryAvailable: true,
      emailDeliveryAvailable: true,
      discordDeliveryAvailable: true,
      updatedAt: null,
    });
    updateNotificationPreferences.mockResolvedValue({
      channel: 'multi',
      enabled: true,
      email: 'alice@example.com',
      emailEnabled: true,
      discordEnabled: true,
      discordWebhook: 'https://discord.com/api/webhooks/999/token',
      deliveryAvailable: true,
      emailDeliveryAvailable: true,
      discordDeliveryAvailable: true,
      updatedAt: '2026-04-15T10:00:00Z',
    });

    render(
      <MemoryRouter>
        <PersonalSettingsPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(getNotificationPreferences).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByLabelText('启用个人邮件通知'));
    fireEvent.change(screen.getByLabelText('通知邮箱'), { target: { value: 'alice@example.com' } });
    fireEvent.click(screen.getByLabelText('启用个人 Discord Webhook 通知'));
    fireEvent.change(screen.getByLabelText('Discord Webhook 地址'), {
      target: { value: 'https://discord.com/api/webhooks/999/token' },
    });
    fireEvent.click(screen.getByRole('button', { name: '保存通知目标' }));

    await waitFor(() => {
      expect(updateNotificationPreferences).toHaveBeenCalledWith({
        emailEnabled: true,
        email: 'alice@example.com',
        discordEnabled: true,
        discordWebhook: 'https://discord.com/api/webhooks/999/token',
      });
    });
    expect(await screen.findByText('个人通知目标已保存。')).toBeInTheDocument();
  });
});
