import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { Menu } from 'lucide-react';
import { Outlet } from 'react-router-dom';
import { Drawer } from '../common/Drawer';
import { SidebarNav } from './SidebarNav';
import { cn } from '../../utils/cn';
import { ThemeToggle } from '../theme/ThemeToggle';
import { ShellRailContext } from './ShellRailContext';

type ShellProps = {
  children?: React.ReactNode;
};

export const Shell: React.FC<ShellProps> = ({ children }) => {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [railContent, setRailContent] = useState<React.ReactNode | null>(null);
  const collapsed = false;
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
    if (!mobileOpen) {
      return undefined;
    }

    const handleResize = () => {
      if (window.innerWidth >= 1024) {
        setMobileOpen(false);
      }
    };

    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, [mobileOpen]);

  return (
    <ShellRailContext.Provider value={railContextValue}>
      <div className="theme-shell dark min-h-screen overflow-x-clip text-foreground">
        <div className="pointer-events-none fixed inset-x-0 top-3 z-40 flex items-start justify-between px-3 lg:hidden">
          <button
            type="button"
            onClick={() => setMobileOpen(true)}
            className="theme-floating-control pointer-events-auto inline-flex h-10 w-10 items-center justify-center rounded-xl text-secondary-text backdrop-blur-xl transition-colors hover:text-foreground"
            aria-label="打开导航菜单"
          >
            <Menu className="h-5 w-5" />
          </button>
          <div className="pointer-events-auto">
            <ThemeToggle />
          </div>
        </div>

        <div className="mx-auto flex min-h-screen w-full max-w-[var(--layout-shell-max)] gap-[var(--layout-gap)] px-2 py-2 sm:px-3 sm:py-3 lg:px-4">
          <aside
            className={cn(
              'theme-sidebar-shell sticky top-3 hidden shrink-0 overflow-hidden rounded-[1.6rem] p-2.5 backdrop-blur-md transition-[width] duration-200 lg:flex',
              'max-h-[calc(100vh-1.5rem)] self-start sm:top-4 sm:max-h-[calc(100vh-2rem)]',
              collapsed ? 'w-[68px]' : 'w-[var(--layout-sidebar-width)]',
            )}
            aria-label="桌面侧边导航"
          >
            <div className="flex h-full min-h-0 w-full flex-col">
              <SidebarNav collapsed={collapsed} onNavigate={() => setMobileOpen(false)} embeddedRail={hasRailContent} />
              {hasRailContent ? (
                <div className="theme-sidebar-divider mt-4 min-h-0 flex-1 overflow-hidden border-t pt-4">
                  {railContent}
                </div>
              ) : (
                <div className="theme-sidebar-divider mt-4 flex-1 border-t pt-4">
                  <div className="theme-panel-subtle flex h-full min-h-[8rem] flex-col justify-between rounded-[1rem] px-4 py-4">
                    <div>
                      <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">Workspace Shell</p>
                      <p className="mt-2 text-sm leading-6 text-secondary-text">
                        统一导航宽度、内容起点与桌面端滚动关系，让首页、问股、持仓和回测共享同一视觉节奏。
                      </p>
                    </div>
                    <p className="mt-4 text-xs leading-5 text-muted-text">
                      Navigation、theme switcher 与内容 rail 现在共用同一套桌面壳层宽度。
                    </p>
                  </div>
                </div>
              )}
            </div>
          </aside>

          <main className="min-h-0 min-w-0 flex-1 pt-14 lg:pt-0">
            {children ?? <Outlet />}
          </main>
        </div>

        <Drawer
          isOpen={mobileOpen}
          onClose={() => setMobileOpen(false)}
          title="导航菜单"
          width="max-w-xs"
          zIndex={90}
          side="left"
        >
          <div className="flex h-full min-h-0 flex-col">
            <SidebarNav onNavigate={() => setMobileOpen(false)} embeddedRail={hasRailContent} />
            {hasRailContent ? (
              <div className="theme-sidebar-divider mt-4 min-h-0 flex-1 overflow-hidden border-t pt-4">
                {railContent}
              </div>
            ) : (
              <div className="theme-sidebar-divider mt-4 border-t pt-4">
                <div className="theme-panel-subtle rounded-[1rem] px-4 py-4 text-sm leading-6 text-secondary-text">
                  当前页面没有附加 rail，但仍沿用统一的壳层宽度和移动端抽屉行为。
                </div>
              </div>
            )}
          </div>
        </Drawer>
      </div>
    </ShellRailContext.Provider>
  );
};
