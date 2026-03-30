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

type TranslateVars = Record<string, string | number | undefined>;

type UiLanguageContextValue = {
  language: UiLanguage;
  setLanguage: (language: UiLanguage) => void;
  toggleLanguage: () => void;
  t: (key: string, vars?: TranslateVars) => string;
};

const defaultLanguage = getStoredUiLanguage();

const defaultContextValue: UiLanguageContextValue = {
  language: defaultLanguage,
  setLanguage: () => undefined,
  toggleLanguage: () => undefined,
  t: (key, vars) => translate(defaultLanguage, key, vars),
};

const UiLanguageContext = createContext<UiLanguageContextValue>(defaultContextValue);

export const UiLanguageProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [language, setLanguageState] = useState<UiLanguage>(() => getStoredUiLanguage());

  useEffect(() => {
    setStoredUiLanguage(language);
    document.documentElement.lang = normalizeUiLanguage(language);
  }, [language]);

  const value = useMemo<UiLanguageContextValue>(() => ({
    language,
    setLanguage: (nextLanguage) => setLanguageState(normalizeUiLanguage(nextLanguage)),
    toggleLanguage: () => setLanguageState((current) => (current === 'zh' ? 'en' : 'zh')),
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
