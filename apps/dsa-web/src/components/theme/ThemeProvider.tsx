/* eslint-disable react-refresh/only-export-components */
import type React from 'react';
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { ThemeProvider as NextThemesProvider } from 'next-themes';

export type ThemeStylePreset = 'terminal' | 'cyber' | 'hacker';

type ThemeStyleContextValue = {
  themeStyle: ThemeStylePreset;
  setThemeStyle: (value: ThemeStylePreset) => void;
};

type ThemeProviderProps = {
  children: React.ReactNode;
};

const THEME_STYLE_STORAGE_KEY = 'dsa-theme-style';
const DEFAULT_THEME_STYLE: ThemeStylePreset = 'terminal';

const ThemeStyleContext = createContext<ThemeStyleContextValue | null>(null);

function isThemeStylePreset(value: string | null): value is ThemeStylePreset {
  return value === 'terminal' || value === 'cyber' || value === 'hacker';
}

const ThemeStyleController: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [themeStyle, setThemeStyleState] = useState<ThemeStylePreset>(() => {
    if (typeof window === 'undefined') {
      return DEFAULT_THEME_STYLE;
    }
    const storedValue = window.localStorage.getItem(THEME_STYLE_STORAGE_KEY);
    return isThemeStylePreset(storedValue) ? storedValue : DEFAULT_THEME_STYLE;
  });

  useEffect(() => {
    if (typeof document === 'undefined') {
      return;
    }

    document.documentElement.dataset.themeStyle = themeStyle;
    document.body.dataset.themeStyle = themeStyle;
    window.localStorage.setItem(THEME_STYLE_STORAGE_KEY, themeStyle);
  }, [themeStyle]);

  const setThemeStyle = useCallback((value: ThemeStylePreset) => {
    setThemeStyleState(value);
  }, []);

  const contextValue = useMemo(
    () => ({
      themeStyle,
      setThemeStyle,
    }),
    [themeStyle, setThemeStyle],
  );

  return (
    <ThemeStyleContext.Provider value={contextValue}>
      {children}
    </ThemeStyleContext.Provider>
  );
};

export function useThemeStyle(): ThemeStyleContextValue {
  const context = useContext(ThemeStyleContext);
  if (!context) {
    throw new Error('useThemeStyle must be used within ThemeProvider');
  }
  return context;
}

export const ThemeProvider: React.FC<ThemeProviderProps> = ({ children }) => {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem={false}
      disableTransitionOnChange
    >
      <ThemeStyleController>{children}</ThemeStyleController>
    </NextThemesProvider>
  );
};
