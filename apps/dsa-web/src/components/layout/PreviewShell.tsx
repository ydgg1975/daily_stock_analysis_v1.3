import type React from 'react';
import { useEffect, useState } from 'react';
import { Menu } from 'lucide-react';
import { Drawer } from '../common/Drawer';
import { ThemeToggle } from '../theme/ThemeToggle';
import { useI18n } from '../../contexts/UiLanguageContext';
import { useIsDesktopViewport } from './useIsDesktopViewport';

type PreviewShellProps = {
  children: React.ReactNode;
};

const PreviewRail: React.FC = () => {
  const { t } = useI18n();

  return (
    <div className="flex h-full min-h-0 w-full flex-col gap-4">
      <div className="theme-sidebar-brand flex items-center justify-between rounded-[1rem] px-4 py-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">Preview Shell</p>
          <p className="mt-1 text-sm font-semibold text-foreground">Responsive report</p>
        </div>
        <div className="shrink-0">
          <ThemeToggle variant="nav" />
        </div>
      </div>
      <div className="theme-panel-subtle rounded-[1rem] px-4 py-4">
        <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">Preview rail</p>
        <p className="mt-2 text-sm leading-6 text-secondary-text">
          开发态壳层单独隔离，用来复用正式环境的 shell 节奏并验证报告在桌面与移动端下的实际布局表现。
        </p>
        <p className="mt-4 text-xs leading-5 text-muted-text">
          {t('shell.workspaceShellFoot')}
        </p>
      </div>
    </div>
  );
};

export const PreviewShell: React.FC<PreviewShellProps> = ({ children }) => {
  const { t } = useI18n();
  const isDesktop = useIsDesktopViewport();
  const [mobileOpen, setMobileOpen] = useState(false);

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
    <div className="theme-shell min-h-screen overflow-x-clip text-foreground" data-testid="preview-shell">
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
          <aside className="theme-sidebar-shell sticky top-3 hidden h-[calc(100vh-1.5rem)] w-[var(--layout-sidebar-width)] shrink-0 self-start overflow-hidden rounded-[1.6rem] p-2.5 lg:flex">
            <PreviewRail />
          </aside>
        ) : null}

        <main className="theme-main-lane min-h-0 min-w-0 flex-1 pt-14 lg:pt-0">
          {children}
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
          <PreviewRail />
        </Drawer>
      ) : null}
    </div>
  );
};
