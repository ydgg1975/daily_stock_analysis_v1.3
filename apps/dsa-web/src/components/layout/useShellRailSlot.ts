import type React from 'react';
import { useEffect } from 'react';
import { useShellRail } from './ShellRailContext';

export function useShellRailSlot(content: React.ReactNode | null): void {
  const { setRailContent } = useShellRail();

  useEffect(() => {
    setRailContent(content);
    return () => {
      setRailContent(null);
    };
  }, [content, setRailContent]);
}
