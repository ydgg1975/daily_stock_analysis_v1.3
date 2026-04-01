import type React from 'react';
import { useMemo, useState } from 'react';
import { ShellRailContext } from '../components/layout/ShellRailContext';

type ShellRailHarnessProps = {
  children: React.ReactNode;
};

export const ShellRailHarness: React.FC<ShellRailHarnessProps> = ({ children }) => {
  const [railContent, setRailContent] = useState<React.ReactNode | null>(null);
  const contextValue = useMemo(
    () => ({
      setRailContent,
      closeMobileRail: () => undefined,
      isConnected: true,
    }),
    [],
  );

  return (
    <ShellRailContext.Provider value={contextValue}>
      <div className="flex min-h-screen">
        <aside data-testid="shell-rail-host" className="w-80 shrink-0">
          {railContent}
        </aside>
        <div className="min-w-0 flex-1">{children}</div>
      </div>
    </ShellRailContext.Provider>
  );
};
