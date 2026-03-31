import React, { useState } from 'react';
import { motion } from 'motion/react';
import { BarChart3, BriefcaseBusiness, Home, LogOut, MessageSquareQuote, Settings2 } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import brandImage from '../../assets/wolfystock-brand.png';
import { useAuth } from '../../contexts/AuthContext';
import { useI18n } from '../../contexts/UiLanguageContext';
import { useAgentChatStore } from '../../stores/agentChatStore';
import { cn } from '../../utils/cn';
import { LanguageToggle } from '../common/LanguageToggle';
import { ConfirmDialog } from '../common/ConfirmDialog';
import { ThemeToggle } from '../theme/ThemeToggle';

type SidebarNavProps = {
  collapsed?: boolean;
  onNavigate?: () => void;
  embeddedRail?: boolean;
};

type NavItem = {
  key: string;
  labelKey: string;
  to: string;
  icon: React.ComponentType<{ className?: string }>;
  exact?: boolean;
  badge?: 'completion';
};

const NAV_ITEMS: NavItem[] = [
  { key: 'home', labelKey: 'nav.home', to: '/', icon: Home, exact: true },
  { key: 'chat', labelKey: 'nav.chat', to: '/chat', icon: MessageSquareQuote, badge: 'completion' },
  { key: 'portfolio', labelKey: 'nav.portfolio', to: '/portfolio', icon: BriefcaseBusiness },
  { key: 'backtest', labelKey: 'nav.backtest', to: '/backtest', icon: BarChart3 },
  { key: 'settings', labelKey: 'nav.settings', to: '/settings', icon: Settings2 },
];

export const SidebarNav: React.FC<SidebarNavProps> = ({ collapsed = false, onNavigate, embeddedRail = false }) => {
  const { authEnabled, logout } = useAuth();
  const { t } = useI18n();
  const completionBadge = useAgentChatStore((state) => state.completionBadge);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);

  return (
    <div className={cn('flex shrink-0 flex-col', embeddedRail ? 'h-auto' : 'h-full')}>
      <div className={cn(embeddedRail ? 'mb-3 flex items-center gap-2 px-1' : 'mb-4 flex items-center gap-2 px-1', collapsed ? 'justify-center' : '')}>
        <div className="theme-sidebar-brand flex h-10 w-10 items-center justify-center overflow-hidden rounded-2xl">
          <img src={brandImage} alt="WolfyStock" className="h-full w-full scale-[1.12] object-cover object-center" />
        </div>
        {!collapsed ? (
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold tracking-[0.06em] text-foreground">WolfyStock</p>
            <p className="truncate text-[10px] uppercase tracking-[0.18em] text-muted-text">{t('nav.terminal')}</p>
          </div>
        ) : null}
      </div>

      <div className={cn(embeddedRail ? 'mb-3 grid gap-2' : 'mb-3 grid gap-2')}>
        <LanguageToggle variant="nav" collapsed={collapsed} />
        <ThemeToggle variant="nav" collapsed={collapsed} />
      </div>

      <nav className={cn('theme-nav flex flex-col', embeddedRail ? '' : 'flex-1')} aria-label={t('shell.drawerTitle')}>
        {NAV_ITEMS.map(({ key, labelKey, to, icon: Icon, exact, badge }) => {
          const label = t(labelKey);
          return (
          <NavLink
            key={key}
            to={to}
            end={exact}
            onClick={onNavigate}
            aria-label={label}
          className={({ isActive }) =>
              cn(
                'theme-nav-item group relative flex items-center gap-3 text-sm transition-all',
                'h-[var(--nav-item-height)]',
                collapsed ? 'justify-center px-0' : 'px-[var(--nav-item-padding-x)]',
                isActive
                  ? 'is-active text-foreground'
                  : 'text-secondary-text hover:text-foreground'
              )
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <motion.div 
                    layoutId="activeIndicator"
                    className="theme-nav-indicator absolute bottom-1.5 left-1.5 top-1.5 bg-[var(--nav-indicator-bg)] shadow-[0_0_8px_var(--nav-indicator-shadow)]"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
                  />
                )}
                <span className={cn('theme-nav-icon-wrap ml-1 inline-flex h-7 w-7 shrink-0 items-center justify-center', collapsed ? 'ml-0' : '')}>
                  <Icon className={cn('h-[1.125rem] w-[1.125rem] shrink-0', isActive ? 'text-[var(--nav-icon-active)]' : 'text-current')} />
                </span>
                {!collapsed ? <span className="truncate">{label}</span> : null}
                {badge === 'completion' && completionBadge ? (
                  <span
                    data-testid="chat-completion-badge"
                    className={cn(
                      'absolute right-3 h-2.5 w-2.5 rounded-full border border-black bg-[var(--nav-badge-bg)] shadow-[0_0_8px_var(--nav-indicator-shadow)]',
                      collapsed ? 'right-2 top-2' : ''
                    )}
                    aria-label={t('nav.chatBadge')}
                  />
                ) : null}
              </>
            )}
          </NavLink>
        )})}
      </nav>

      {authEnabled ? (
        <button
          type="button"
          onClick={() => setShowLogoutConfirm(true)}
          className={cn(
            'theme-panel-subtle mt-5 flex h-11 w-full cursor-pointer select-none items-center gap-3 rounded-2xl px-3 text-sm text-secondary-text transition-all hover:text-foreground',
            collapsed ? 'justify-center px-2' : ''
          )}
        >
          <LogOut className="h-5 w-5 shrink-0" />
          {!collapsed ? <span>{t('nav.logout')}</span> : null}
        </button>
      ) : null}

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
    </div>
  );
};
