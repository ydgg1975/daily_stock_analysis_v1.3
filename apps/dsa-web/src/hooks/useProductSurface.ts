import { useEffect, useSyncExternalStore } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { getStoredUiLanguage } from '../i18n/core';
import { buildLocalizedPath, parseLocaleFromPathname, shouldLocalizePath } from '../utils/localeRouting';

export type ProductSurfaceRole = 'guest' | 'user' | 'admin';
export type AdminSurfaceMode = 'user' | 'admin';

const ADMIN_SURFACE_MODE_STORAGE_KEY = 'dsa-admin-surface-mode';

let adminSurfaceModeSnapshot: AdminSurfaceMode = 'user';
const adminSurfaceModeListeners = new Set<() => void>();

function getAdminSurfaceModeSnapshot(): AdminSurfaceMode {
  return adminSurfaceModeSnapshot;
}

function getAdminSurfaceModeServerSnapshot(): AdminSurfaceMode {
  return 'user';
}

function subscribeAdminSurfaceMode(listener: () => void): () => void {
  adminSurfaceModeListeners.add(listener);
  return () => {
    adminSurfaceModeListeners.delete(listener);
  };
}

function readStoredAdminSurfaceMode(): AdminSurfaceMode {
  if (typeof window === 'undefined') {
    return 'user';
  }
  const stored = window.sessionStorage.getItem(ADMIN_SURFACE_MODE_STORAGE_KEY);
  return stored === 'admin' ? 'admin' : 'user';
}

function publishAdminSurfaceMode(nextMode: AdminSurfaceMode): void {
  adminSurfaceModeSnapshot = nextMode;
  if (typeof window !== 'undefined') {
    window.sessionStorage.setItem(ADMIN_SURFACE_MODE_STORAGE_KEY, nextMode);
  }
  adminSurfaceModeListeners.forEach((listener) => listener());
}

export function setAdminSurfaceMode(mode: AdminSurfaceMode): void {
  const normalizedMode: AdminSurfaceMode = mode === 'admin' ? 'admin' : 'user';
  if (normalizedMode === adminSurfaceModeSnapshot) {
    if (typeof window !== 'undefined') {
      window.sessionStorage.setItem(ADMIN_SURFACE_MODE_STORAGE_KEY, normalizedMode);
    }
    return;
  }
  publishAdminSurfaceMode(normalizedMode);
}

if (typeof window !== 'undefined') {
  adminSurfaceModeSnapshot = readStoredAdminSurfaceMode();
}

export function resolveProductSurfaceRole(params: {
  authEnabled: boolean;
  loggedIn: boolean;
  currentUser: { isAdmin?: boolean } | null;
}): ProductSurfaceRole {
  if (params.currentUser?.isAdmin) {
    return 'admin';
  }
  if (params.authEnabled && !params.loggedIn) {
    return 'guest';
  }
  return 'user';
}

export function normalizeRedirectPath(
  redirectTo: string | null | undefined,
  fallback = '/',
): string {
  const normalized = typeof redirectTo === 'string' && redirectTo.startsWith('/') && !redirectTo.startsWith('//')
    ? redirectTo
    : fallback;
  return normalized.startsWith('/') && !normalized.startsWith('//') ? normalized : fallback;
}

export function resolveAuthRedirect(search: string, fallback = '/'): string {
  return normalizeRedirectPath(new URLSearchParams(search).get('redirect'), fallback);
}

function resolveActiveLocale() {
  if (typeof window === 'undefined') {
    return getStoredUiLanguage();
  }
  const routeLocale = parseLocaleFromPathname(window.location.pathname);
  return routeLocale || getStoredUiLanguage();
}

export function buildLoginPath(redirectTo: string): string {
  const normalizedRedirect = normalizeRedirectPath(redirectTo);
  const activeLocale = resolveActiveLocale();
  const localizedRedirect = buildLocalizedPath(normalizedRedirect, activeLocale);
  const path = `/login?redirect=${encodeURIComponent(localizedRedirect)}`;
  if (typeof window !== 'undefined' && shouldLocalizePath(window.location.pathname)) {
    return buildLocalizedPath(path, activeLocale);
  }
  return path;
}

export function buildRegistrationPath(redirectTo: string): string {
  const normalizedRedirect = normalizeRedirectPath(redirectTo);
  const activeLocale = resolveActiveLocale();
  const localizedRedirect = buildLocalizedPath(normalizedRedirect, activeLocale);
  const path = `/login?mode=create&redirect=${encodeURIComponent(localizedRedirect)}`;
  if (typeof window !== 'undefined' && shouldLocalizePath(window.location.pathname)) {
    return buildLocalizedPath(path, activeLocale);
  }
  return path;
}

export function useProductSurface() {
  const { authEnabled, loggedIn, currentUser } = useAuth();
  const storedAdminSurfaceMode = useSyncExternalStore(
    subscribeAdminSurfaceMode,
    getAdminSurfaceModeSnapshot,
    getAdminSurfaceModeServerSnapshot,
  );
  const role = resolveProductSurfaceRole({ authEnabled, loggedIn, currentUser });
  const isAdminAccount = role === 'admin';

  useEffect(() => {
    if (!isAdminAccount && storedAdminSurfaceMode !== 'user') {
      setAdminSurfaceMode('user');
    }
  }, [isAdminAccount, storedAdminSurfaceMode]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    const handleStorage = (event: StorageEvent) => {
      if (event.key !== ADMIN_SURFACE_MODE_STORAGE_KEY) {
        return;
      }
      adminSurfaceModeSnapshot = event.newValue === 'admin' ? 'admin' : 'user';
      adminSurfaceModeListeners.forEach((listener) => listener());
    };
    window.addEventListener('storage', handleStorage);
    return () => {
      window.removeEventListener('storage', handleStorage);
    };
  }, []);

  const surfaceMode: AdminSurfaceMode = isAdminAccount ? storedAdminSurfaceMode : 'user';
  const isAdminMode = isAdminAccount && surfaceMode === 'admin';
  const isUserMode = !isAdminMode;

  return {
    role,
    authEnabled,
    loggedIn,
    currentUser,
    isGuest: role === 'guest',
    isUser: role === 'user',
    isAdmin: role === 'admin',
    isAdminAccount,
    surfaceMode,
    isAdminMode,
    isUserMode,
    isAuthenticated: role !== 'guest',
    setAdminSurfaceMode,
    toggleAdminSurfaceMode: () => setAdminSurfaceMode(isAdminMode ? 'user' : 'admin'),
  };
}
