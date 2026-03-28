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
      <div className="dark min-h-screen bg-[#020202] text-foreground">
        <div className="pointer-events-none fixed inset-x-0 top-3 z-40 flex items-start justify-between px-3 lg:hidden">
          <button
            type="button"
            onClick={() => setMobileOpen(true)}
            className="pointer-events-auto inline-flex h-10 w-10 items-center justify-center rounded-xl border border-white/8 bg-[#080808]/88 text-secondary-text shadow-[0_16px_36px_rgba(0,0,0,0.28)] backdrop-blur-xl transition-colors hover:bg-white/[0.06] hover:text-foreground"
            aria-label="打开导航菜单"
          >
            <Menu className="h-5 w-5" />
          </button>
          <div className="pointer-events-auto">
            <ThemeToggle />
          </div>
        </div>

        <div className="flex min-h-screen w-full px-2 py-2 sm:px-3 sm:py-3 lg:px-4">
          <aside
            className={cn(
              'sticky top-3 hidden shrink-0 overflow-hidden rounded-[1.6rem] border border-white/8 bg-[#050505]/94 p-2.5 shadow-[0_22px_54px_rgba(0,0,0,0.34)] backdrop-blur-md transition-[width] duration-200 lg:flex',
              'max-h-[calc(100vh-1.5rem)] self-start sm:top-4 sm:max-h-[calc(100vh-2rem)]',
              collapsed ? 'w-[68px]' : hasRailContent ? 'w-[320px] xl:w-[336px] 2xl:w-[352px]' : 'w-[128px]',
            )}
            aria-label="桌面侧边导航"
          >
            <div className="flex h-full min-h-0 w-full flex-col">
              <SidebarNav collapsed={collapsed} onNavigate={() => setMobileOpen(false)} embeddedRail={hasRailContent} />
              {hasRailContent ? (
                <div className="mt-4 min-h-0 flex-1 overflow-hidden border-t border-white/7 pt-4">
                  {railContent}
                </div>
              ) : null}
            </div>
          </aside>

          <main className="min-h-0 min-w-0 flex-1 pt-14 lg:pl-4 lg:pt-0">
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
              <div className="mt-4 min-h-0 flex-1 overflow-hidden border-t border-white/7 pt-4">
                {railContent}
              </div>
            ) : null}
          </div>
        </Drawer>
      </div>
    </ShellRailContext.Provider>
  );
};
