/**
 * SpaceX live refactor: preserves routing, archive access, language toggling,
 * completion badge, and logout confirmation while shifting navigation to a
 * restrained text-first shell with subtle active/hover states and no boxed tabs.
 */
import React, { useEffect, useMemo, useState } from 'react';
import {
  Archive,
  BriefcaseBusiness,
  Globe,
  Home,
  LogOut,
  MessageSquareText,
  Settings2,
  TestTubeDiagonal,
} from 'lucide-react';
import { NavLink, useLocation } from 'react-router-dom';
import { agentApi } from '../../api/agent';
import { useAuth } from '../../contexts/AuthContext';
import { useI18n } from '../../contexts/UiLanguageContext';
import { useAgentChatStore } from '../../stores/agentChatStore';
import { cn } from '../../utils/cn';
import { ConfirmDialog } from '../common/ConfirmDialog';

type SidebarNavProps = {
  layout?: 'header' | 'drawer';
  onNavigate?: () => void;
  onOpenArchive?: () => void;
  hasArchive?: boolean;
};

type NavItem = {
  key: string;
  labelKey: string;
  to: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: 'completion';
};

const BrandWordmark: React.FC<{
  onNavigate?: () => void;
  className?: string;
}> = ({ onNavigate, className }) => (
  <NavLink
    to="/"
    end
    onClick={onNavigate}
    aria-label="WolfyStock"
    className={({ isActive }) => cn('shell-brand-link', className || '', isActive ? 'is-active' : '')}
  >
    <span className="shell-wordmark">WolfyStock</span>
  </NavLink>
);

const NAV_ITEMS: NavItem[] = [
  { key: 'home', labelKey: 'nav.home', to: '/', icon: Home },
  { key: 'chat', labelKey: 'nav.chat', to: '/chat', icon: MessageSquareText, badge: 'completion' },
  { key: 'portfolio', labelKey: 'nav.portfolio', to: '/portfolio', icon: BriefcaseBusiness },
  { key: 'backtest', labelKey: 'nav.backtest', to: '/backtest', icon: TestTubeDiagonal },
  { key: 'settings', labelKey: 'nav.settings', to: '/settings', icon: Settings2 },
];

function NavLabel({
  label,
  showBadge,
}: {
  label: string;
  showBadge: boolean;
}) {
  return (
    <span className="relative inline-flex min-w-0 items-center gap-2">
      <span>{label}</span>
      {showBadge ? (
        <span
          data-testid="chat-completion-badge"
          className="shell-nav-dot"
          aria-label={label}
        />
      ) : null}
    </span>
  );
}

function DrawerUtilityLabel({
  label,
  value,
}: {
  label: string;
  value?: string;
}) {
  return (
    <span className="shell-nav-item__copy">
      <span className="shell-nav-item__label">{label}</span>
      {value ? <span className="shell-nav-item__value">{value}</span> : null}
    </span>
  );
}

export const SidebarNav: React.FC<SidebarNavProps> = ({
  layout = 'header',
  onNavigate,
  onOpenArchive,
  hasArchive = false,
}) => {
  const location = useLocation();
  const { authEnabled, logout } = useAuth();
  const { language, t, toggleLanguage } = useI18n();
  const completionBadge = useAgentChatStore((state) => state.completionBadge);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);
  const [agentEnabled, setAgentEnabled] = useState<boolean>(location.pathname.startsWith('/chat'));
  const isDrawer = layout === 'drawer';

  useEffect(() => {
    let cancelled = false;

    void agentApi.getStatus()
      .then((payload) => {
        if (!cancelled) {
          setAgentEnabled(payload.enabled);
        }
      })
      .catch(() => {
        if (!cancelled && location.pathname.startsWith('/chat')) {
          setAgentEnabled(true);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [location.pathname]);

  const visibleNavItems = useMemo(
    () => NAV_ITEMS.filter((item) => item.key !== 'chat' || agentEnabled),
    [agentEnabled],
  );

  const navLinks = visibleNavItems.map(({ key, labelKey, to, icon: Icon, badge }) => {
    const label = t(labelKey);
    return (
      <NavLink
        key={key}
        to={to}
        end={to === '/'}
        onClick={onNavigate}
        aria-label={label}
        className={({ isActive }) => cn(
          isDrawer ? 'shell-drawer-link' : 'shell-header-link',
          isActive ? 'is-active' : '',
        )}
      >
        {isDrawer ? (
          <span className="shell-nav-item__icon" aria-hidden="true">
            <Icon className="h-4 w-4" />
          </span>
        ) : null}
        <span className={isDrawer ? 'shell-nav-item__label' : 'shell-header-link__label'}>
          <NavLabel label={label} showBadge={badge === 'completion' && completionBadge} />
        </span>
      </NavLink>
    );
  });

  const archiveAction = hasArchive ? (
    <button
      type="button"
      onClick={() => {
        onOpenArchive?.();
        onNavigate?.();
      }}
      className={isDrawer ? 'shell-nav-item shell-nav-item--utility' : 'shell-header-action'}
      aria-label={t('shell.archiveTitle')}
    >
      {isDrawer ? (
        <>
          <span className="shell-nav-item__icon" aria-hidden="true">
            <Archive className="h-4 w-4" />
          </span>
          <DrawerUtilityLabel label={t('shell.archiveTitle')} />
        </>
      ) : (
        <span>{t('shell.archiveShort')}</span>
      )}
    </button>
  ) : null;

  const languageAction = (
    <button
      type="button"
      onClick={() => {
        toggleLanguage();
        onNavigate?.();
      }}
      className={isDrawer ? 'shell-nav-item shell-nav-item--utility' : 'shell-header-action'}
      aria-label={t('language.toggle')}
    >
      {isDrawer ? (
        <>
          <span className="shell-nav-item__icon" aria-hidden="true">
            <Globe className="h-4 w-4" />
          </span>
          <DrawerUtilityLabel
            label={t('language.toggle')}
            value={language === 'zh' ? t('language.zh') : t('language.en')}
          />
        </>
      ) : (
        <span>{language === 'zh' ? 'EN' : 'ZH'}</span>
      )}
    </button>
  );

  const logoutAction = authEnabled ? (
    <button
      type="button"
      onClick={() => setShowLogoutConfirm(true)}
      className={isDrawer ? 'shell-nav-item shell-nav-item--utility shell-nav-item--danger' : 'shell-header-action shell-header-action--danger'}
      aria-label={t('nav.logout')}
    >
      {isDrawer ? (
        <>
          <span className="shell-nav-item__icon" aria-hidden="true">
            <LogOut className="h-4 w-4" />
          </span>
          <DrawerUtilityLabel label={t('nav.logout')} />
        </>
      ) : (
        <span>{t('nav.logout')}</span>
      )}
    </button>
  ) : null;

  return (
    <>
      {isDrawer ? (
        <div className="shell-drawer-nav">
          <div className="shell-drawer-brand">
            <BrandWordmark onNavigate={onNavigate} />
            <span className="shell-drawer-note">{t('nav.terminal')}</span>
          </div>
          <nav className="shell-drawer-links" aria-label={t('shell.drawerTitle')}>
            {navLinks}
          </nav>
          <div className="shell-drawer-footer">
            {archiveAction}
            {languageAction}
            {logoutAction}
          </div>
        </div>
      ) : (
        <div className="shell-header-nav">
          <div className="shell-header-brand">
            <BrandWordmark />
          </div>
          <nav className="shell-header-links" aria-label={t('shell.drawerTitle')}>
            {navLinks}
          </nav>
          <div className="shell-header-utilities">
            {archiveAction}
            {languageAction}
            {logoutAction}
          </div>
        </div>
      )}

      <ConfirmDialog
        isOpen={showLogoutConfirm}
        title={t('nav.logoutTitle')}
        message={t('nav.logoutMessage')}
        confirmText={t('nav.logoutConfirm')}
        cancelText={t('nav.logoutCancel')}
        isDanger
        onConfirm={() => {
          setShowLogoutConfirm(false);
          onNavigate?.();
          void logout();
        }}
        onCancel={() => setShowLogoutConfirm(false)}
      />
    </>
  );
};
