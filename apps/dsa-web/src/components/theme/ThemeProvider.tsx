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
import { ThemeProvider as NextThemesProvider, useTheme } from 'next-themes';

export type ThemeStylePreset = 'spacex';
type RootThemeName = 'spacex';

type ThemeStyleContextValue = {
  themeStyle: ThemeStylePreset;
  setThemeStyle: (value: ThemeStylePreset) => void;
};

type ThemeProviderProps = {
  children: React.ReactNode;
};

const THEME_STYLE_STORAGE_KEY = 'dsa-theme-style';
const DEFAULT_THEME_STYLE: ThemeStylePreset = 'spacex';

const ThemeStyleContext = createContext<ThemeStyleContextValue | null>(null);

function toRootThemeName(style: ThemeStylePreset): RootThemeName {
  return style;
}

const ThemeStyleController: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { setTheme } = useTheme();
  const [themeStyle] = useState<ThemeStylePreset>(DEFAULT_THEME_STYLE);

  useEffect(() => {
    if (typeof document === 'undefined') {
      return;
    }

    const rootTheme = toRootThemeName(themeStyle);
    const colorMode = 'dark';
    document.documentElement.classList.remove('light');
    document.documentElement.classList.add('dark');
    document.documentElement.dataset.theme = rootTheme;
    document.body.dataset.theme = rootTheme;
    document.documentElement.dataset.colorMode = colorMode;
    document.body.dataset.colorMode = colorMode;
    window.localStorage.setItem(THEME_STYLE_STORAGE_KEY, themeStyle);
    void setTheme(colorMode);
  }, [setTheme, themeStyle]);

  const setThemeStyle = useCallback(() => undefined, []);

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
