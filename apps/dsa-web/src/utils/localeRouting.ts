import { normalizeUiLanguage, type UiLanguage } from '../i18n/core';

const LOCALE_SEGMENTS = new Set<UiLanguage>(['zh', 'en']);

export function parseLocaleFromPathname(pathname: string | null | undefined): UiLanguage | null {
  const normalizedPath = String(pathname || '').trim();
  if (!normalizedPath.startsWith('/')) {
    return null;
  }
  const segment = normalizedPath.split('/')[1];
  if (!segment || !LOCALE_SEGMENTS.has(segment as UiLanguage)) {
    return null;
  }
  return segment as UiLanguage;
}

export function stripLocalePrefix(pathname: string | null | undefined): string {
  const normalizedPath = String(pathname || '').trim();
  const locale = parseLocaleFromPathname(normalizedPath);
  if (!locale) {
    return normalizedPath.startsWith('/') ? normalizedPath || '/' : '/';
  }
  const stripped = normalizedPath.slice(locale.length + 1);
  return stripped.startsWith('/') ? stripped : stripped ? `/${stripped}` : '/';
}

export function buildLocalizedPath(path: string, language: UiLanguage): string {
  const normalizedLanguage = normalizeUiLanguage(language);
  const [pathnameWithMaybeQuery, hashFragment = ''] = String(path || '/').split('#', 2);
  const [pathnamePart = '/', searchPart = ''] = pathnameWithMaybeQuery.split('?', 2);
  const normalizedPath = stripLocalePrefix(pathnamePart || '/');
  const prefixedPath = normalizedPath === '/'
    ? `/${normalizedLanguage}`
    : `/${normalizedLanguage}${normalizedPath}`;
  const search = searchPart ? `?${searchPart}` : '';
  const hash = hashFragment ? `#${hashFragment}` : '';
  return `${prefixedPath}${search}${hash}`;
}

export function shouldLocalizePath(pathname: string | null | undefined): boolean {
  const normalizedPath = String(pathname || '').trim();
  return normalizedPath.startsWith('/') && !normalizedPath.startsWith('/__preview/');
}
