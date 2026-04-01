import { useEffect, useState } from 'react';

export function getIsDesktopViewport(): boolean {
  if (typeof window === 'undefined') {
    return true;
  }
  return window.innerWidth >= 1024;
}

export function useIsDesktopViewport(): boolean {
  const [isDesktop, setIsDesktop] = useState(getIsDesktopViewport);

  useEffect(() => {
    const handleResize = () => {
      setIsDesktop(getIsDesktopViewport());
    };

    handleResize();
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  return isDesktop;
}
