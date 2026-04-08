/* eslint-disable react-refresh/only-export-components */
import type React from 'react';
import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import {
  DEFAULT_MARKET_COLOR_CONVENTION,
  getMarketColorPalette,
  MARKET_COLOR_CONVENTION_STORAGE_KEY,
  normalizeMarketColorConvention,
  type MarketColorConvention,
} from '../utils/marketColors';

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
  marketColorConvention: MarketColorConvention;
  setMarketColorConvention: (value: MarketColorConvention) => void;
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

function getStoredMarketColorConvention(): MarketColorConvention {
  if (typeof window === 'undefined') {
    return DEFAULT_MARKET_COLOR_CONVENTION;
  }
  return normalizeMarketColorConvention(
    window.localStorage.getItem(MARKET_COLOR_CONVENTION_STORAGE_KEY),
  );
}

const defaultContext: UiPreferencesContextValue = {
  fontSize: getStoredFontSize(),
  setFontSize: () => undefined,
  marketColorConvention: getStoredMarketColorConvention(),
  setMarketColorConvention: () => undefined,
};

const UiPreferencesContext = createContext<UiPreferencesContextValue>(defaultContext);

export const UiPreferencesProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [fontSize, setFontSizeState] = useState<UiFontSize>(() => getStoredFontSize());
  const [marketColorConvention, setMarketColorConventionState] = useState<MarketColorConvention>(
    () => getStoredMarketColorConvention(),
  );

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

  useEffect(() => {
    const normalized = normalizeMarketColorConvention(marketColorConvention);
    const palette = getMarketColorPalette(normalized);
    document.documentElement.style.setProperty('--market-up-hsl', palette.upHsl);
    document.documentElement.style.setProperty('--market-down-hsl', palette.downHsl);
    document.documentElement.setAttribute('data-market-color-convention', normalized);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(MARKET_COLOR_CONVENTION_STORAGE_KEY, normalized);
    }
  }, [marketColorConvention]);

  const value = useMemo<UiPreferencesContextValue>(() => ({
    fontSize,
    setFontSize: (size) => setFontSizeState(normalizeFontSize(size)),
    marketColorConvention,
    setMarketColorConvention: (value) => {
      setMarketColorConventionState(normalizeMarketColorConvention(value));
    },
  }), [fontSize, marketColorConvention]);

  return (
    <UiPreferencesContext.Provider value={value}>
      {children}
    </UiPreferencesContext.Provider>
  );
};

export function useUiPreferences(): UiPreferencesContextValue {
  return useContext(UiPreferencesContext);
}
