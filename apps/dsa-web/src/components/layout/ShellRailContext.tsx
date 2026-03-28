import type React from 'react';
import { createContext, useContext } from 'react';

type ShellRailContextValue = {
  setRailContent: (content: React.ReactNode | null) => void;
  closeMobileRail: () => void;
  isConnected: boolean;
};

export const ShellRailContext = createContext<ShellRailContextValue>({
  setRailContent: () => undefined,
  closeMobileRail: () => undefined,
  isConnected: false,
});

export const useShellRail = () => useContext(ShellRailContext);
