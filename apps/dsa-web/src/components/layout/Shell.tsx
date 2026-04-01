import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { Menu } from 'lucide-react';
import { Outlet } from 'react-router-dom';
import { Drawer } from '../common/Drawer';
import { SidebarNav } from './SidebarNav';
import { cn } from '../../utils/cn';
import { ShellRailContext } from './ShellRailContext';
import { useI18n } from '../../contexts/UiLanguageContext';
import { useIsDesktopViewport } from './useIsDesktopViewport';

type ShellProps = {
  children?: React.ReactNode;
};

type ShellRailBodyProps = {
  hasRailContent: boolean;
  railContent: React.ReactNode | null;
  onNavigate: () => void;
  emptyContent: React.ReactNode;
};

const ShellRailBody: React.FC<ShellRailBodyProps> = ({
  hasRailContent,
  railContent,
  onNavigate,
  emptyContent,
}) => (
  <div className="flex h-full min-h-0 flex-col">
    <SidebarNav onNavigate={onNavigate} embeddedRail={hasRailContent} />
    {hasRailContent ? (
      <div className="theme-sidebar-divider mt-4 min-h-0 flex-1 overflow-hidden border-t pt-4">
        {railContent}
      </div>
    ) : (
      <div className="theme-sidebar-divider mt-4 flex-1 border-t pt-4">
        {emptyContent}
      </div>
    )}
  </div>
);

export const Shell: React.FC<ShellProps> = ({ children }) => {
  const { t } = useI18n();
  const isDesktop = useIsDesktopViewport();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [railContent, setRailContent] = useState<React.ReactNode | null>(null);
  const hasRailContent = Boolean(railContent);

  const railContextValue = useMemo(
    () => ({
      setRailContent,
      closeMobileRail: () => setMobileOpen(false),
      isConnected: true,
    }),
    [],
  );

  useEffect(() => {
    if (!isDesktop) {
      return undefined;
    }

    const frame = window.requestAnimationFrame(() => {
      setMobileOpen(false);
    });

    return () => {
      window.cancelAnimationFrame(frame);
    };
  }, [isDesktop]);

  return (
    <ShellRailContext.Provider value={railContextValue}>
      <div className="theme-shell min-h-screen overflow-x-clip text-foreground">
        {!isDesktop ? (
          <div className="pointer-events-none fixed left-3 top-3 z-40">
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              className="theme-floating-control pointer-events-auto inline-flex h-10 w-10 items-center justify-center rounded-xl text-secondary-text backdrop-blur-xl transition-colors hover:text-foreground"
              aria-label={t('shell.openMenu')}
            >
              <Menu className="h-5 w-5" />
            </button>
          </div>
        ) : null}

        <div className="mx-auto flex min-h-screen w-full max-w-[var(--layout-shell-max)] gap-[var(--layout-shell-gap,var(--layout-gap))] px-2 py-2 sm:px-3 sm:py-3 lg:px-4">
          {isDesktop ? (
            <aside
              className={cn(
                'theme-sidebar-shell sticky top-3 hidden shrink-0 overflow-hidden rounded-[1.6rem] backdrop-blur-md transition-[width,box-shadow,border-color,background] duration-220 ease-out lg:flex',
                'h-[calc(100vh-1.5rem)] self-start sm:top-4 sm:h-[calc(100vh-2rem)]',
                'w-[var(--layout-sidebar-width)]',
              )}
              aria-label="桌面侧边导航"
            >
              <ShellRailBody
                hasRailContent={hasRailContent}
                railContent={railContent}
                onNavigate={() => setMobileOpen(false)}
                emptyContent={
                  <div className="theme-panel-subtle flex h-full min-h-[8rem] flex-col justify-between rounded-[1rem] px-4 py-4">
                    <div>
                      <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">Workspace Shell</p>
                      <p className="mt-2 text-sm leading-6 text-secondary-text">
                        {t('shell.workspaceShellBody')}
                      </p>
                    </div>
                    <p className="mt-4 text-xs leading-5 text-muted-text">
                      {t('shell.workspaceShellFoot')}
                    </p>
                  </div>
                }
              />
            </aside>
          ) : null}

          <main className="theme-main-lane min-h-0 min-w-0 flex-1 pt-14 lg:pt-0">
            {children ?? <Outlet />}
          </main>
        </div>

        {!isDesktop ? (
          <Drawer
            isOpen={mobileOpen}
            onClose={() => setMobileOpen(false)}
            title={t('shell.drawerTitle')}
            width="max-w-xs"
            zIndex={90}
            side="left"
          >
            <ShellRailBody
              hasRailContent={hasRailContent}
              railContent={railContent}
              onNavigate={() => setMobileOpen(false)}
              emptyContent={
                <div className="theme-panel-subtle rounded-[1rem] px-4 py-4 text-sm leading-6 text-secondary-text">
                  {t('shell.noRail')}
                </div>
              }
            />
          </Drawer>
        ) : null}
      </div>
    </ShellRailContext.Provider>
  );
};
