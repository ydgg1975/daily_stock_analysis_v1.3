import React, { useState } from 'react';
import { motion } from 'motion/react';
import { BarChart3, Bell, BriefcaseBusiness, Home, LineChart, LogOut, MessageSquareQuote, Settings2 } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useAgentChatStore } from '../../stores/agentChatStore';
import { cn } from '../../utils/cn';
import { ConfirmDialog } from '../common/ConfirmDialog';
import { StatusDot } from '../common/StatusDot';
import { ThemeToggle } from '../theme/ThemeToggle';

type SidebarNavProps = {
  collapsed?: boolean;
  onNavigate?: () => void;
};

type NavItem = {
  key: string;
  label: string;
  to: string;
  icon: React.ComponentType<{ className?: string }>;
  exact?: boolean;
  badge?: 'completion';
};

const NAV_ITEMS: NavItem[] = [
  { key: 'home', label: '\uD648', to: '/', icon: Home, exact: true },
  { key: 'chat', label: 'AI \uC885\uBAA9 \uC0C1\uB2F4', to: '/chat', icon: MessageSquareQuote, badge: 'completion' },
  { key: 'portfolio', label: '\uD3EC\uD2B8\uD3F4\uB9AC\uC624', to: '/portfolio', icon: BriefcaseBusiness },
  { key: 'charts', label: '\uCC28\uD2B8 \uBD84\uC11D', to: '/charts', icon: LineChart },
  { key: 'backtest', label: '\uBC31\uD14C\uC2A4\uD2B8', to: '/backtest', icon: BarChart3 },
  { key: 'alerts', label: '\uC54C\uB9BC', to: '/alerts', icon: Bell },
  { key: 'settings', label: '\uC124\uC815', to: '/settings', icon: Settings2 },
];

export const SidebarNav: React.FC<SidebarNavProps> = ({ collapsed = false, onNavigate }) => {
  const { authEnabled, logout } = useAuth();
  const completionBadge = useAgentChatStore((state) => state.completionBadge);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);

  return (
    <div className="flex h-full flex-col">
      <div className={cn('mb-4 flex items-center gap-2 px-1', collapsed ? 'justify-center' : '')}>
        <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-primary-gradient text-[hsl(var(--primary-foreground))] shadow-[0_12px_28px_var(--nav-brand-shadow)]">
          <BarChart3 className="h-5 w-5" />
        </div>
        {!collapsed ? (
          <p className="min-w-0 truncate text-sm font-semibold text-foreground">DSA</p>
        ) : null}
      </div>

      <nav className="flex flex-1 flex-col gap-1.5" aria-label="주 메뉴">
        {NAV_ITEMS.map(({ key, label, to, icon: Icon, exact, badge }) => (
          <NavLink
            key={key}
            to={to}
            end={exact}
            onClick={onNavigate}
            aria-label={label}
            className={({ isActive }) =>
              cn(
                'group relative flex items-center gap-3 border-y border-x-0 text-sm transition-all',
                'h-[var(--nav-item-height)]',
                collapsed ? 'justify-center px-0' : 'px-[var(--nav-item-padding-x)]',
                isActive
                  ? 'border-[var(--nav-active-border)] bg-[var(--nav-active-bg)] text-[hsl(var(--primary))] font-medium'
                  : 'border-transparent text-secondary-text hover:bg-[var(--nav-hover-bg)] hover:text-foreground',
              )
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <motion.div
                    layoutId="activeIndicator"
                    className="absolute top-0 bottom-0 left-0 w-[var(--nav-indicator-width)] bg-[var(--nav-indicator-bg)] shadow-[0_0_10px_var(--nav-indicator-shadow)]"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 0.2 }}
                  />
                )}
                <Icon className={cn('ml-1 h-5 w-5 shrink-0', isActive ? 'text-[var(--nav-icon-active)]' : 'text-current')} />
                {!collapsed ? <span className="truncate">{label}</span> : null}
                {badge === 'completion' && completionBadge ? (
                  <StatusDot
                    tone="info"
                    data-testid="chat-completion-badge"
                    className={cn(
                      'absolute right-3 border-2 border-background shadow-[0_0_10px_var(--nav-indicator-shadow)]',
                      collapsed ? 'right-2 top-2' : '',
                    )}
                    aria-label="AI 종목 상담 새 메시지"
                  />
                ) : null}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="mt-4 mb-2">
        <ThemeToggle variant="nav" collapsed={collapsed} />
      </div>

      {authEnabled ? (
        <button
          type="button"
          onClick={() => setShowLogoutConfirm(true)}
          className={cn(
            'mt-5 flex h-11 w-full cursor-pointer select-none items-center gap-3 rounded-2xl border border-transparent px-3 text-sm text-secondary-text transition-all hover:border-border/70 hover:bg-hover hover:text-foreground',
            collapsed ? 'justify-center px-2' : '',
          )}
        >
          <LogOut className="h-5 w-5 shrink-0" />
          {!collapsed ? <span>로그아웃</span> : null}
        </button>
      ) : null}

      <ConfirmDialog
        isOpen={showLogoutConfirm}
        title="로그아웃"
        message="현재 로그인 상태에서 나가시겠습니까? 다시 접속하려면 비밀번호를 입력해야 합니다."
        confirmText="로그아웃"
        cancelText="취소"
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
