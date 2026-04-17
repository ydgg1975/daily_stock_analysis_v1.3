/* eslint-disable react-refresh/only-export-components */
import type React from 'react';
import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import {
  getStoredUiLanguage,
  normalizeUiLanguage,
  setStoredUiLanguage,
  translate,
  type UiLanguage,
} from '../i18n/core';
import { buildLocalizedPath, parseLocaleFromPathname, shouldLocalizePath } from '../utils/localeRouting';

type TranslateVars = Record<string, string | number | undefined>;

type UiLanguageContextValue = {
  language: UiLanguage;
  setLanguage: (language: UiLanguage) => void;
  toggleLanguage: () => void;
  t: (key: string, vars?: TranslateVars) => string;
};

function resolveInitialLanguage(): UiLanguage {
  if (typeof window !== 'undefined') {
    const routeLanguage = parseLocaleFromPathname(window.location.pathname);
    if (routeLanguage) {
      return routeLanguage;
    }
  }
  return getStoredUiLanguage();
}

function syncCurrentPathToLanguage(nextLanguage: UiLanguage): void {
  if (typeof window === 'undefined' || !shouldLocalizePath(window.location.pathname)) {
    return;
  }
  const currentPath = `${window.location.pathname}${window.location.search}${window.location.hash}`;
  const nextPath = buildLocalizedPath(currentPath, nextLanguage);
  if (nextPath === currentPath) {
    return;
  }
  window.history.replaceState(window.history.state, '', nextPath);
  window.dispatchEvent(new PopStateEvent('popstate'));
}

const defaultLanguage = resolveInitialLanguage();

const defaultContextValue: UiLanguageContextValue = {
  language: defaultLanguage,
  setLanguage: () => undefined,
  toggleLanguage: () => undefined,
  t: (key, vars) => translate(defaultLanguage, key, vars),
};

const UiLanguageContext = createContext<UiLanguageContextValue>(defaultContextValue);

export const UiLanguageProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [language, setLanguageState] = useState<UiLanguage>(() => resolveInitialLanguage());

  useEffect(() => {
    setStoredUiLanguage(language);
    document.documentElement.lang = normalizeUiLanguage(language);
  }, [language]);

  const value = useMemo<UiLanguageContextValue>(() => ({
    language,
    setLanguage: (nextLanguage) => {
      const normalized = normalizeUiLanguage(nextLanguage);
      syncCurrentPathToLanguage(normalized);
      setLanguageState(normalized);
    },
    toggleLanguage: () => setLanguageState((current) => {
      const nextLanguage = current === 'zh' ? 'en' : 'zh';
      syncCurrentPathToLanguage(nextLanguage);
      return nextLanguage;
    }),
    t: (key, vars) => translate(language, key, vars),
  }), [language]);

  return (
    <UiLanguageContext.Provider value={value}>
      {children}
    </UiLanguageContext.Provider>
  );
};

export function useI18n(): UiLanguageContextValue {
  return useContext(UiLanguageContext);
}
