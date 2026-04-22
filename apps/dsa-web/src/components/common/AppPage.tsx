/**
 * AppPage — standard wrapper for every tab/page rendered inside <Shell>.
 *
 * Layout rules (enforced by this component + convention across pages):
 *   - Page roots must use <AppPage> so height/width follow the flex shell.
 *   - DO NOT use viewport-relative units on page roots:
 *       100vh / 100dvh / h-screen / min-h-screen / calc(100vh - *)
 *     They escape the Shell's max-width/sidebar layout and cause
 *     the "top spans the full page" bug.
 *   - For pages with an internal scroll region (chat, long lists):
 *       wrap content in: h-full overflow-hidden flex flex-col
 *       scroll area: flex-1 min-h-0 overflow-y-auto
 */
import type React from 'react';
import { cn } from '../../utils/cn';

interface AppPageProps {
  children: React.ReactNode;
  className?: string;
}

export const AppPage: React.FC<AppPageProps> = ({ children, className = '' }) => {
  return (
    <main className={cn('mx-auto min-h-full w-full max-w-7xl px-4 pb-8 pt-4 md:px-6 lg:px-8', className)}>
      {children}
    </main>
  );
};
