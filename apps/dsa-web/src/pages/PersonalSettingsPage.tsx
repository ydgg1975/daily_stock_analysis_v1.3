import type React from 'react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { BellRing, LockKeyhole, ShieldCheck, SlidersHorizontal } from 'lucide-react';
import { ApiErrorAlert, Card, WorkspacePageHeader } from '../components/common';
import { authApi, type UserNotificationPreferences } from '../api/auth';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import { ChangePasswordCard } from '../components/settings/ChangePasswordCard';
import { FontSizeSettingsCard } from '../components/settings/FontSizeSettingsCard';
import { useI18n } from '../contexts/UiLanguageContext';
import { useUiPreferences } from '../contexts/UiPreferencesContext';
import { useAuth } from '../contexts/AuthContext';
import { buildLoginPath, buildRegistrationPath, useProductSurface } from '../hooks/useProductSurface';
import type { MarketColorConvention } from '../utils/marketColors';

const MARKET_COLOR_OPTIONS: Array<{
  value: MarketColorConvention;
  labelKey: string;
  descriptionKey: string;
}> = [
  {
    value: 'redDownGreenUp',
    labelKey: 'settings.marketColorConventional',
    descriptionKey: 'settings.marketColorConventionalDesc',
  },
  {
    value: 'redUpGreenDown',
    labelKey: 'settings.marketColorCn',
    descriptionKey: 'settings.marketColorCnDesc',
  },
];

const PersonalSettingsPage: React.FC = () => {
  const { language, setLanguage, t } = useI18n();
  const { marketColorConvention, setMarketColorConvention } = useUiPreferences();
  const { authEnabled, passwordChangeable } = useAuth();
  const {
    isGuest,
    isAdmin,
    isAdminMode,
    loggedIn,
    currentUser,
    setAdminSurfaceMode,
  } = useProductSurface();
  const [notificationPrefs, setNotificationPrefs] = useState<UserNotificationPreferences | null>(null);
  const [notificationEmail, setNotificationEmail] = useState('');
  const [notificationEmailEnabled, setNotificationEmailEnabled] = useState(false);
  const [notificationDiscordEnabled, setNotificationDiscordEnabled] = useState(false);
  const [notificationDiscordWebhook, setNotificationDiscordWebhook] = useState('');
  const [notificationLoading, setNotificationLoading] = useState(false);
  const [notificationSaving, setNotificationSaving] = useState(false);
  const [notificationError, setNotificationError] = useState<ParsedApiError | null>(null);
  const [notificationNotice, setNotificationNotice] = useState<string | null>(null);
  const loginPath = buildLoginPath('/settings');
  const registrationPath = buildRegistrationPath('/settings');

  useEffect(() => {
    document.title = language === 'en' ? 'Settings - WolfyStock' : '设置 - WolfyStock';
  }, [language]);

  useEffect(() => {
    if (!loggedIn) {
      setNotificationPrefs(null);
      setNotificationEmail('');
      setNotificationEmailEnabled(false);
      setNotificationDiscordEnabled(false);
      setNotificationDiscordWebhook('');
      setNotificationLoading(false);
      setNotificationSaving(false);
      setNotificationError(null);
      setNotificationNotice(null);
      return;
    }

    let cancelled = false;
    setNotificationLoading(true);
    setNotificationError(null);
    void authApi.getNotificationPreferences()
      .then((prefs) => {
        if (cancelled) {
          return;
        }
        setNotificationPrefs(prefs);
        setNotificationEmail(prefs.email || '');
        setNotificationEmailEnabled(Boolean(prefs.emailEnabled));
        setNotificationDiscordEnabled(Boolean(prefs.discordEnabled));
        setNotificationDiscordWebhook(prefs.discordWebhook || '');
      })
      .catch((err) => {
        if (cancelled) {
          return;
        }
        setNotificationError(getParsedApiError(err));
      })
      .finally(() => {
        if (!cancelled) {
          setNotificationLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [loggedIn]);

  const handleSaveNotificationPreferences = async () => {
    setNotificationSaving(true);
    setNotificationError(null);
    setNotificationNotice(null);
    try {
      const prefs = await authApi.updateNotificationPreferences(
        {
          emailEnabled: notificationEmailEnabled,
          email: notificationEmail.trim() || null,
          discordEnabled: notificationDiscordEnabled,
          discordWebhook: notificationDiscordWebhook.trim() || null,
        },
      );
      setNotificationPrefs(prefs);
      setNotificationEmail(prefs.email || '');
      setNotificationEmailEnabled(Boolean(prefs.emailEnabled));
      setNotificationDiscordEnabled(Boolean(prefs.discordEnabled));
      setNotificationDiscordWebhook(prefs.discordWebhook || '');
      setNotificationNotice(
        language === 'en'
          ? 'Personal notification targets saved.'
          : '个人通知目标已保存。',
      );
    } catch (err) {
      setNotificationError(getParsedApiError(err));
    } finally {
      setNotificationSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <WorkspacePageHeader
        eyebrow={language === 'en' ? 'Personal Settings' : '个人设置'}
        title={language === 'en' ? 'Workspace preferences' : '工作区偏好'}
        description={language === 'en'
          ? 'Keep appearance, readability, and personal session controls separate from system-level operator configuration.'
          : '将外观、可读性和个人会话控制，与系统级 operator 配置明确分开。'}
      />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.08fr)_minmax(22rem,0.92fr)]">
        <Card title={language === 'en' ? 'Interface preferences' : '界面偏好'} subtitle={language === 'en' ? 'Local to this browser' : '仅保存在当前浏览器'}>
          <div className="grid gap-4 xl:grid-cols-2">
            <div className="settings-surface rounded-[var(--theme-panel-radius-md)] border settings-border px-4 py-4">
              <p className="text-[11px] uppercase tracking-[0.14em] font-semibold text-foreground">{t('settings.languageTitle')}</p>
              <p className="mt-1 text-xs leading-5 text-muted-text">{t('settings.languageDesc')}</p>
              <div className="mt-3 grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setLanguage('zh')}
                  className={language === 'zh'
                    ? 'rounded-[var(--theme-control-radius)] border border-[var(--border-strong)] bg-[var(--pill-active-bg)] px-3 py-2 text-xs font-semibold uppercase tracking-widest text-foreground shadow-[var(--glow-soft)]'
                    : 'rounded-[var(--theme-control-radius)] border border-[var(--border-muted)] bg-[var(--pill-bg)] px-3 py-2 text-xs font-semibold uppercase tracking-widest text-secondary-text hover:border-[var(--border-strong)] hover:text-foreground'}
                  aria-pressed={language === 'zh'}
                >
                  {t('language.zh')}
                </button>
                <button
                  type="button"
                  onClick={() => setLanguage('en')}
                  className={language === 'en'
                    ? 'rounded-[var(--theme-control-radius)] border border-[var(--border-strong)] bg-[var(--pill-active-bg)] px-3 py-2 text-xs font-semibold uppercase tracking-widest text-foreground shadow-[var(--glow-soft)]'
                    : 'rounded-[var(--theme-control-radius)] border border-[var(--border-muted)] bg-[var(--pill-bg)] px-3 py-2 text-xs font-semibold uppercase tracking-widest text-secondary-text hover:border-[var(--border-strong)] hover:text-foreground'}
                  aria-pressed={language === 'en'}
                >
                  {t('language.en')}
                </button>
              </div>
            </div>

            <div className="settings-surface rounded-[var(--theme-panel-radius-md)] border settings-border px-4 py-4">
              <p className="text-[11px] uppercase tracking-[0.14em] font-semibold text-foreground">{t('settings.marketColorTitle')}</p>
              <p className="mt-1 text-xs leading-5 text-muted-text">{t('settings.marketColorDesc')}</p>
              <div className="mt-3 space-y-2">
                {MARKET_COLOR_OPTIONS.map((option) => {
                  const active = marketColorConvention === option.value;
                  return (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => setMarketColorConvention(option.value)}
                      className={active
                        ? 'w-full rounded-[var(--theme-control-radius)] border border-[var(--border-strong)] bg-[var(--pill-active-bg)] px-3 py-2 text-left shadow-[var(--glow-soft)]'
                        : 'w-full rounded-[var(--theme-control-radius)] border border-[var(--border-muted)] bg-[var(--pill-bg)] px-3 py-2 text-left hover:border-[var(--border-strong)]'}
                      aria-pressed={active}
                    >
                      <p className="text-sm font-medium text-foreground">{t(option.labelKey)}</p>
                      <p className="mt-1 text-xs text-muted-text">{t(option.descriptionKey)}</p>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          <div className="mt-4">
            <FontSizeSettingsCard />
          </div>
        </Card>

        <Card title={language === 'en' ? 'Access layer' : '访问层'} subtitle={language === 'en' ? 'Role-aware product surface' : '角色感知产品面'}>
          <div className="space-y-4">
            {isGuest && authEnabled ? (
              <div className="rounded-[var(--theme-panel-radius-md)] border border-[hsl(var(--accent-warning-hsl)/0.28)] bg-[hsl(var(--accent-warning-hsl)/0.12)] px-4 py-4">
                <div className="flex items-start gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full border border-[hsl(var(--accent-warning-hsl)/0.32)] bg-[hsl(var(--accent-warning-hsl)/0.18)] text-[hsl(var(--accent-warning-hsl))]">
                    <LockKeyhole className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-foreground">
                      {language === 'en' ? 'Guest preferences only' : '当前仅为游客偏好'}
                    </p>
                    <p className="mt-1 text-xs leading-5 text-secondary-text">
                      {language === 'en'
                        ? 'Your appearance settings are stored locally, but personal history, chat, portfolio, and scanner data still require sign-in.'
                        : '你的外观偏好会保存在本地，但个人历史、问股、持仓和扫描器数据仍然需要登录后才会拥有。'}
                    </p>
                  </div>
                </div>
                <div className="mt-4 flex flex-wrap gap-3">
                  <Link
                    to={loginPath}
                    className="inline-flex min-h-[40px] items-center justify-center rounded-[var(--theme-button-radius)] border border-transparent bg-[var(--pill-active-bg)] px-4 text-[0.75rem] text-foreground transition-colors hover:border-[var(--border-strong)]"
                  >
                    {language === 'en' ? 'Sign in to unlock personal data' : '登录后解锁个人数据'}
                  </Link>
                  <Link
                    to={registrationPath}
                    className="inline-flex min-h-[40px] items-center justify-center rounded-[var(--theme-button-radius)] border border-[var(--border-muted)] bg-[var(--pill-bg)] px-4 text-[0.75rem] text-secondary-text transition-colors hover:border-[var(--border-strong)] hover:text-foreground"
                  >
                    {language === 'en' ? 'Create account' : '创建账户'}
                  </Link>
                </div>
              </div>
            ) : null}

            {!isGuest ? (
              <div className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/45 px-4 py-4">
                <div className="flex items-start gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/6 text-foreground">
                    <ShieldCheck className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-foreground">
                      {language === 'en'
                        ? `Signed in as ${currentUser?.displayName || currentUser?.username || 'user'}`
                        : `当前身份：${currentUser?.displayName || currentUser?.username || '用户'}`}
                    </p>
                    <p className="mt-1 text-xs leading-5 text-secondary-text">
                      {language === 'en'
                        ? 'Analysis history, chat sessions, portfolio data, scanner runs, and backtests now resolve against your authenticated identity.'
                        : '分析历史、问股会话、持仓数据、扫描器运行结果与回测现在都会按你的已认证身份解析。'}
                    </p>
                  </div>
                </div>
              </div>
            ) : null}

            {isAdmin ? (
              <div className="rounded-[var(--theme-panel-radius-md)] border border-[hsl(var(--accent-positive-hsl)/0.26)] bg-[hsl(var(--accent-positive-hsl)/0.1)] px-4 py-4">
                <div className="flex items-start gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full border border-[hsl(var(--accent-positive-hsl)/0.26)] bg-[hsl(var(--accent-positive-hsl)/0.16)] text-[hsl(var(--accent-positive-hsl))]">
                    <SlidersHorizontal className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-foreground">
                      {language === 'en' ? 'Admin mode split' : 'Admin 模式分层'}
                    </p>
                    <p className="mt-1 text-xs leading-5 text-secondary-text">
                      {language === 'en'
                        ? 'Your admin account now defaults to a normal user-like surface. Operator tools stay behind an explicit Admin Mode switch.'
                        : '你的管理员账户现在默认先以普通用户形态进入产品，operator 工具会继续留在显式的 Admin Mode 开关之后。'}
                    </p>
                  </div>
                </div>
                <div className="mt-4 flex flex-wrap items-center gap-3">
                  <button
                    type="button"
                    onClick={() => setAdminSurfaceMode(isAdminMode ? 'user' : 'admin')}
                    className="inline-flex min-h-[40px] items-center justify-center rounded-[var(--theme-button-radius)] border border-transparent bg-[var(--pill-active-bg)] px-4 text-[0.75rem] text-foreground transition-colors hover:border-[var(--border-strong)]"
                  >
                    {isAdminMode
                      ? (language === 'en' ? 'Return to User Mode' : '返回 User Mode')
                      : (language === 'en' ? 'Enter Admin Mode' : '进入 Admin Mode')}
                  </button>
                  <span className="inline-flex min-h-[40px] items-center justify-center rounded-[var(--theme-button-radius)] border border-[var(--border-muted)] bg-[var(--pill-bg)] px-4 text-[0.75rem] text-secondary-text">
                    {isAdminMode
                      ? (language === 'en' ? 'Current surface: Admin Mode' : '当前产品面：Admin Mode')
                      : (language === 'en' ? 'Current surface: User Mode' : '当前产品面：User Mode')}
                  </span>
                </div>
                <div className="mt-4 flex flex-wrap gap-3">
                  {isAdminMode ? (
                    <>
                      <Link
                        to="/settings/system"
                        className="inline-flex min-h-[40px] items-center justify-center rounded-[var(--theme-button-radius)] border border-transparent bg-[var(--pill-active-bg)] px-4 text-[0.75rem] text-foreground transition-colors hover:border-[var(--border-strong)]"
                      >
                        {language === 'en' ? 'Open system settings' : '进入系统设置'}
                      </Link>
                      <Link
                        to="/admin/logs"
                        className="inline-flex min-h-[40px] items-center justify-center rounded-[var(--theme-button-radius)] border border-[var(--border-muted)] bg-[var(--pill-bg)] px-4 text-[0.75rem] text-secondary-text transition-colors hover:border-[var(--border-strong)] hover:text-foreground"
                      >
                        {language === 'en' ? 'Open admin logs' : '查看管理员日志'}
                      </Link>
                    </>
                  ) : (
                    <p className="text-xs leading-5 text-secondary-text">
                      {language === 'en'
                        ? 'Stay in User Mode for everyday analysis, then switch into Admin Mode only when you need system settings or operator logs.'
                        : '日常分析先停留在 User Mode，只有需要系统设置或 operator 日志时再显式切换到 Admin Mode。'}
                    </p>
                  )}
                </div>
              </div>
            ) : null}

            <div className="grid gap-3 md:grid-cols-2">
              <div className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/45 px-4 py-4">
                <div className="flex items-center gap-3">
                  <BellRing className="h-4 w-4 text-foreground" />
                  <p className="text-sm font-semibold text-foreground">
                    {language === 'en' ? 'Personal notification posture' : '个人通知语境'}
                  </p>
                </div>
                {loggedIn ? (
                  <div className="mt-3 space-y-3">
                    <p className="text-xs leading-5 text-secondary-text">
                      {language === 'en'
                        ? 'Personal analysis notifications now resolve to your own email and Discord targets instead of reusing admin/system channels.'
                        : '个人分析通知现在会解析到你自己的邮箱与 Discord 目标，不再复用 admin/system 通道。'}
                    </p>
                    <label className="flex items-center gap-3 text-xs text-secondary-text">
                      <input
                        type="checkbox"
                        className="h-4 w-4 rounded border border-[var(--border-muted)] bg-transparent"
                        checked={notificationEmailEnabled}
                        onChange={(event) => setNotificationEmailEnabled(event.target.checked)}
                        disabled={notificationLoading || notificationSaving}
                      />
                      <span>{language === 'en' ? 'Enable personal email notifications' : '启用个人邮件通知'}</span>
                    </label>
                    <label className="block">
                      <span className="theme-field-label">{language === 'en' ? 'Notification email' : '通知邮箱'}</span>
                      <input
                        type="email"
                        value={notificationEmail}
                        onChange={(event) => setNotificationEmail(event.target.value)}
                        placeholder={language === 'en' ? 'you@example.com' : 'name@example.com'}
                        disabled={notificationLoading || notificationSaving}
                        className="mt-2 w-full rounded-[var(--theme-control-radius)] border border-[var(--border-muted)] bg-[var(--pill-bg)] px-3 py-2 text-sm text-foreground outline-none transition-colors focus:border-[var(--border-strong)]"
                      />
                    </label>
                    {!notificationPrefs?.emailDeliveryAvailable ? (
                      <p className="text-xs leading-5 text-secondary-text">
                        {language === 'en'
                          ? 'System email delivery is not configured yet, so this personal target will stay saved but inactive until an admin enables outbound email.'
                          : '系统邮件发送尚未配置，因此这个个人目标会先保存下来，等管理员启用发信能力后才会真正生效。'}
                      </p>
                    ) : null}
                    <label className="flex items-center gap-3 text-xs text-secondary-text">
                      <input
                        type="checkbox"
                        className="h-4 w-4 rounded border border-[var(--border-muted)] bg-transparent"
                        checked={notificationDiscordEnabled}
                        onChange={(event) => setNotificationDiscordEnabled(event.target.checked)}
                        disabled={notificationLoading || notificationSaving}
                      />
                      <span>{language === 'en' ? 'Enable personal Discord webhook notifications' : '启用个人 Discord Webhook 通知'}</span>
                    </label>
                    <label className="block">
                      <span className="theme-field-label">{language === 'en' ? 'Discord webhook URL' : 'Discord Webhook 地址'}</span>
                      <input
                        type="url"
                        value={notificationDiscordWebhook}
                        onChange={(event) => setNotificationDiscordWebhook(event.target.value)}
                        placeholder="https://discord.com/api/webhooks/..."
                        disabled={notificationLoading || notificationSaving}
                        className="mt-2 w-full rounded-[var(--theme-control-radius)] border border-[var(--border-muted)] bg-[var(--pill-bg)] px-3 py-2 text-sm text-foreground outline-none transition-colors focus:border-[var(--border-strong)]"
                      />
                    </label>
                    <p className="text-xs leading-5 text-secondary-text">
                      {language === 'en'
                        ? 'Discord delivery uses the webhook you provide here and stays separate from shared operator channels.'
                        : 'Discord 通知会使用你在这里填写的 Webhook，并继续与共享的 operator 通道保持分离。'}
                    </p>
                    {notificationNotice ? (
                      <p className="text-xs leading-5 text-[hsl(var(--accent-positive-hsl))]">{notificationNotice}</p>
                    ) : null}
                    {notificationError ? <ApiErrorAlert error={notificationError} /> : null}
                    <button
                      type="button"
                      onClick={() => void handleSaveNotificationPreferences()}
                      disabled={notificationLoading || notificationSaving}
                      className="inline-flex min-h-[40px] items-center justify-center rounded-[var(--theme-button-radius)] border border-transparent bg-[var(--pill-active-bg)] px-4 text-[0.75rem] text-foreground transition-colors hover:border-[var(--border-strong)] disabled:pointer-events-none disabled:opacity-50"
                    >
                      {notificationSaving
                        ? (language === 'en' ? 'Saving...' : '保存中...')
                        : (language === 'en' ? 'Save notification target' : '保存通知目标')}
                    </button>
                  </div>
                ) : (
                  <p className="mt-2 text-xs leading-5 text-secondary-text">
                    {language === 'en'
                      ? 'This phase keeps notification channel internals under admin control. Personal preferences stay lightweight here.'
                      : '本阶段仍将通知通道内部配置保留在 admin 控制面，个人偏好在这里保持轻量。'}
                  </p>
                )}
              </div>
              <div className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/45 px-4 py-4">
                <div className="flex items-center gap-3">
                  <ShieldCheck className="h-4 w-4 text-foreground" />
                  <p className="text-sm font-semibold text-foreground">
                    {language === 'en' ? 'System split stays explicit' : '系统分层保持显式'}
                  </p>
                </div>
                <p className="mt-2 text-xs leading-5 text-secondary-text">
                  {language === 'en'
                    ? 'Normal users only see harmless local preferences here. System knobs stay out of the default settings surface.'
                    : '普通用户在这里仅看到无害的本地偏好，系统级开关不会再出现在默认设置面。'}
                </p>
              </div>
            </div>
          </div>
        </Card>
      </div>

      {loggedIn && passwordChangeable ? <ChangePasswordCard /> : null}
    </div>
  );
};

export default PersonalSettingsPage;
