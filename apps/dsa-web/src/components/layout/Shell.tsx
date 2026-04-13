/**
 * SpaceX live refactor: keeps routing, drawer orchestration, and rail injection
 * unchanged while tightening the masthead and content shell around a more
 * restrained text-first navigation system.
 */
import type React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Menu } from 'lucide-react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { Drawer } from '../common/Drawer';
import { SidebarNav } from './SidebarNav';
import { ShellRailContext } from './ShellRailContext';
import { useI18n } from '../../contexts/UiLanguageContext';
import { useIsDesktopViewport } from './useIsDesktopViewport';

type ShellProps = {
  children?: React.ReactNode;
};

function resolveRailTitle(pathname: string, t: (key: string) => string): string {
  if (pathname.startsWith('/chat')) {
    return t('shell.chatArchiveTitle');
  }
  return t('shell.archiveTitle');
}

function resolveRailDescription(pathname: string, t: (key: string) => string): string {
  if (pathname.startsWith('/chat')) {
    return t('shell.chatArchiveDesc');
  }
  return t('shell.archiveDesc');
}

const ShellRailPanel: React.FC<{
  pathname: string;
  railContent: React.ReactNode;
}> = ({ pathname, railContent }) => {
  const { t } = useI18n();

  return (
    <section className="shell-context-panel">
      <div className="shell-context-panel__header">
        <p className="shell-context-panel__eyebrow">{t('shell.archiveEyebrow')}</p>
        <h2 className="shell-context-panel__title">{resolveRailTitle(pathname, t)}</h2>
        <p className="shell-context-panel__body">{resolveRailDescription(pathname, t)}</p>
      </div>
      <div className="shell-context-panel__content">
        {railContent}
      </div>
    </section>
  );
};

export const Shell: React.FC<ShellProps> = ({ children }) => {
  const { t } = useI18n();
  const location = useLocation();
  const isBacktestRoute = location.pathname.startsWith('/backtest');
  const isDesktop = useIsDesktopViewport();
  const previousPathnameRef = useRef(location.pathname);
  const didInitializeViewportRef = useRef(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [railOpen, setRailOpen] = useState(false);
  const [railContent, setRailContent] = useState<React.ReactNode | null>(null);
  const hasRailContent = Boolean(railContent);
  const isMobileNavVisible = mobileNavOpen;
  const isRailVisible = hasRailContent && railOpen;

  const closeMobileNav = useCallback(() => {
    setMobileNavOpen(false);
  }, []);

  const openMobileNav = useCallback(() => {
    setRailOpen(false);
    setMobileNavOpen(true);
  }, []);

  const closeRail = useCallback(() => {
    setRailOpen(false);
  }, []);

  const openRail = useCallback(() => {
    setMobileNavOpen(false);
    setRailOpen(true);
  }, []);

  const railContextValue = useMemo(
    () => ({
      setRailContent,
      closeMobileRail: closeRail,
      openRail,
      isConnected: true,
    }),
    [closeRail, openRail],
  );

  useEffect(() => {
    if (location.pathname === previousPathnameRef.current) {
      return;
    }

    previousPathnameRef.current = location.pathname;
    const timer = window.setTimeout(() => {
      setMobileNavOpen(false);
      setRailOpen(false);
    }, 0);

    return () => window.clearTimeout(timer);
  }, [location.pathname]);

  useEffect(() => {
    if (!didInitializeViewportRef.current) {
      didInitializeViewportRef.current = true;
      return;
    }

    const timer = window.setTimeout(() => {
      setMobileNavOpen(false);
      setRailOpen(false);
    }, 0);

    return () => window.clearTimeout(timer);
  }, [isDesktop]);

  return (
    <ShellRailContext.Provider value={railContextValue}>
      <div className="theme-shell min-h-screen overflow-x-hidden text-foreground" data-layout={isDesktop ? 'desktop' : 'mobile'}>
        <header className="shell-masthead">
          <div className="shell-masthead__inner">
            {isDesktop ? (
              <SidebarNav
                layout="header"
                onNavigate={closeRail}
                hasArchive={hasRailContent}
                onOpenArchive={openRail}
              />
            ) : (
              <div className="shell-mobile-strip">
                <button
                  type="button"
                  onClick={openMobileNav}
                  className="shell-mobile-button"
                  aria-label={t('shell.openMenu')}
                >
                  <Menu className="h-4 w-4" />
                </button>
                <NavLink to="/" end className="shell-mobile-brand shell-brand-link" aria-label="WolfyStock">
                  <span className="shell-wordmark">WolfyStock</span>
                  <span className="shell-mobile-brand__note">{t('nav.terminal')}</span>
                </NavLink>
                <span className="shell-mobile-placeholder" aria-hidden="true" />
              </div>
            )}
          </div>
        </header>

        <div className={`shell-content-frame${isBacktestRoute ? ' shell-content-frame--backtest' : ''}`}>
          <main className="theme-main-lane shell-main-column">
            <div key={location.pathname} className="theme-page-transition">
              {children ?? <Outlet />}
            </div>
          </main>
        </div>

        {!isDesktop ? (
          <Drawer
            isOpen={isMobileNavVisible}
            onClose={closeMobileNav}
            title={t('shell.drawerTitle')}
            width="max-w-xs"
            zIndex={90}
            side="left"
            closeOnBackdropClick={false}
          >
            <SidebarNav
              layout="drawer"
              onNavigate={closeMobileNav}
              hasArchive={hasRailContent}
              onOpenArchive={openRail}
            />
          </Drawer>
        ) : null}

        {hasRailContent ? (
          <Drawer
            isOpen={isRailVisible}
            onClose={closeRail}
            title={resolveRailTitle(location.pathname, t)}
            width="max-w-[min(92vw,31rem)]"
            zIndex={95}
            side="right"
          >
            <ShellRailPanel pathname={location.pathname} railContent={railContent!} />
          </Drawer>
        ) : null}
      </div>
    </ShellRailContext.Provider>
  );
};
