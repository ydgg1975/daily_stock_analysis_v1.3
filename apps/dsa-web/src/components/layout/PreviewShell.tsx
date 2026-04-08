import type React from 'react';
import { useState } from 'react';
import { Menu } from 'lucide-react';
import { Drawer } from '../common/Drawer';
import { useI18n } from '../../contexts/UiLanguageContext';
import { useIsDesktopViewport } from './useIsDesktopViewport';

type PreviewShellProps = {
  children: React.ReactNode;
};

const PreviewRail: React.FC = () => (
  <div className="shell-context-panel">
    <div className="shell-context-panel__header">
      <p className="shell-context-panel__eyebrow">Preview</p>
      <h2 className="shell-context-panel__title">Report Surface</h2>
      <p className="shell-context-panel__body">
        开发态预览壳层复用正式环境的 SpaceX 结构语言，用来检查报告与响应式行为是否仍然成立。
      </p>
    </div>
  </div>
);

export const PreviewShell: React.FC<PreviewShellProps> = ({ children }) => {
  const { t } = useI18n();
  const isDesktop = useIsDesktopViewport();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="theme-shell min-h-screen overflow-x-hidden text-foreground" data-testid="preview-shell">
      <header className="shell-masthead">
        <div className="shell-masthead__inner">
          {isDesktop ? (
            <div className="shell-nav-strip">
              <div className="shell-nav-brand">
                <span className="shell-wordmark">WolfyStock</span>
                <span className="shell-nav-brand-note">Preview Shell</span>
              </div>
              <div className="shell-nav-actions">
                <button type="button" className="shell-nav-utility">
                  Report Surface
                </button>
              </div>
            </div>
          ) : (
            <div className="shell-mobile-strip">
              <button
                type="button"
                onClick={() => setMobileOpen(true)}
                className="shell-mobile-button"
                aria-label={t('shell.openMenu')}
              >
                <Menu className="h-4 w-4" />
              </button>
              <div className="shell-mobile-brand">
                <span className="shell-wordmark">Preview</span>
                <span className="shell-mobile-brand__note">Report Surface</span>
              </div>
              <span className="shell-mobile-placeholder" aria-hidden="true" />
            </div>
          )}
        </div>
      </header>

      <div className="shell-content-frame">
        <main className="theme-main-lane">
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
