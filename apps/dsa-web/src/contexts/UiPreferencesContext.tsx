/* eslint-disable react-refresh/only-export-components */
import type React from 'react';
import { createContext, useContext, useEffect, useMemo, useState } from 'react';

export type UiFontSize = 'xs' | 's' | 'm' | 'l' | 'xl';

const UI_FONT_SIZE_STORAGE_KEY = 'dsa-ui-font-size';

const FONT_SCALE_DESKTOP_MAP: Record<UiFontSize, number> = {
  xs: 0.9,
  s: 0.95,
  m: 1,
  l: 1.06,
  xl: 1.12,
};

const FONT_SCALE_MOBILE_MAP: Record<UiFontSize, number> = {
  xs: 0.88,
  s: 0.94,
  m: 1,
  l: 1.05,
  xl: 1.1,
};

type UiPreferencesContextValue = {
  fontSize: UiFontSize;
  setFontSize: (size: UiFontSize) => void;
};

function normalizeFontSize(value?: string | null): UiFontSize {
  if (value === 'xs' || value === 's' || value === 'm' || value === 'l' || value === 'xl') {
    return value;
  }
  // Backward compatibility for old persisted options.
  if (value === 'small') {
    return 's';
  }
  if (value === 'large') {
    return 'l';
  }
  return 'm';
}

function getStoredFontSize(): UiFontSize {
  if (typeof window === 'undefined') {
    return 'm';
  }
  return normalizeFontSize(window.localStorage.getItem(UI_FONT_SIZE_STORAGE_KEY));
}

const defaultContext: UiPreferencesContextValue = {
  fontSize: getStoredFontSize(),
  setFontSize: () => undefined,
};

const UiPreferencesContext = createContext<UiPreferencesContextValue>(defaultContext);

export const UiPreferencesProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [fontSize, setFontSizeState] = useState<UiFontSize>(() => getStoredFontSize());

  useEffect(() => {
    const normalized = normalizeFontSize(fontSize);
    const desktopScale = FONT_SCALE_DESKTOP_MAP[normalized];
    const mobileScale = FONT_SCALE_MOBILE_MAP[normalized];
    document.documentElement.style.setProperty('--ui-font-scale-desktop', String(desktopScale));
    document.documentElement.style.setProperty('--ui-font-scale-mobile', String(mobileScale));
    document.documentElement.setAttribute('data-ui-font-size', normalized);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(UI_FONT_SIZE_STORAGE_KEY, normalized);
    }
  }, [fontSize]);

  const value = useMemo<UiPreferencesContextValue>(() => ({
    fontSize,
    setFontSize: (size) => setFontSizeState(normalizeFontSize(size)),
  }), [fontSize]);

  return (
    <UiPreferencesContext.Provider value={value}>
      {children}
    </UiPreferencesContext.Provider>
  );
};

export function useUiPreferences(): UiPreferencesContextValue {
  return useContext(UiPreferencesContext);
}
