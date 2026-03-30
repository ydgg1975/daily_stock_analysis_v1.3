import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { authApi } from '../api/auth';
import { getParsedApiError } from '../api/error';
import { setSystemConfigAdminUnlockToken } from '../api/systemConfig';
import { ApiErrorAlert, Button, Input } from '../components/common';
import { useThemeStyle, type ThemeStylePreset } from '../components/theme/ThemeProvider';
import { useI18n } from '../contexts/UiLanguageContext';
import { useAuth, useSystemConfig } from '../hooks';
import type { SystemConfigCategory } from '../types/systemConfig';
import { getCategoryDescription } from '../utils/systemConfigI18n';
import {
  AuthSettingsCard,
  ChangePasswordCard,
  FontSizeSettingsCard,
  IntelligentImport,
  LLMChannelEditor,
  SettingsAlert,
  SettingsCategoryNav,
  SettingsField,
  SettingsLoading,
  SettingsSectionCard,
} from '../components/settings';

const ADMIN_UNLOCK_TOKEN_STORAGE_KEY = 'dsa-admin-settings-unlock-token';
const ADMIN_UNLOCK_EXPIRES_AT_STORAGE_KEY = 'dsa-admin-settings-unlock-expires-at';

const THEME_OPTIONS: Array<{
  value: ThemeStylePreset;
  labelKey: string;
  descriptionKey: string;
}> = [
  {
    value: 'terminal',
    labelKey: 'theme.terminal',
    descriptionKey: 'theme.terminalDesc',
  },
  {
    value: 'cyber',
    labelKey: 'theme.cyber',
    descriptionKey: 'theme.cyberDesc',
  },
  {
    value: 'hacker',
    labelKey: 'theme.hacker',
    descriptionKey: 'theme.hackerDesc',
  },
];

const SettingsPage: React.FC = () => {
  const { language, setLanguage, t } = useI18n();
  const { passwordChangeable, setupState } = useAuth();
  const { themeStyle, setThemeStyle } = useThemeStyle();

  const [adminPassword, setAdminPassword] = useState('');
  const [adminPasswordConfirm, setAdminPasswordConfirm] = useState('');
  const [isUnlocking, setIsUnlocking] = useState(false);
  const [isAdminUnlocked, setIsAdminUnlocked] = useState(false);
  const [unlockExpiresAt, setUnlockExpiresAt] = useState<number | null>(null);
  const [adminUnlockError, setAdminUnlockError] = useState<string | null>(null);

  const requiresInitialPasswordConfirm = setupState === 'no_password';

  const {
    categories,
    itemsByCategory,
    issueByKey,
    activeCategory,
    setActiveCategory,
    hasDirty,
    dirtyCount,
    toast,
    clearToast,
    isLoading,
    isSaving,
    loadError,
    saveError,
    retryAction,
    load,
    retry,
    save,
    resetDraft,
    setDraftValue,
    refreshAfterExternalSave,
    configVersion,
    maskToken,
  } = useSystemConfig();

  const clearAdminUnlockState = useCallback(() => {
    setIsAdminUnlocked(false);
    setUnlockExpiresAt(null);
    setAdminPassword('');
    setAdminPasswordConfirm('');
    setSystemConfigAdminUnlockToken(null);

    if (typeof window !== 'undefined') {
      window.sessionStorage.removeItem(ADMIN_UNLOCK_TOKEN_STORAGE_KEY);
      window.sessionStorage.removeItem(ADMIN_UNLOCK_EXPIRES_AT_STORAGE_KEY);
    }
  }, []);

  const relockAdminSettings = useCallback(() => {
    clearAdminUnlockState();
    setAdminUnlockError(null);
    resetDraft();
  }, [clearAdminUnlockState, resetDraft]);

  useEffect(() => {
    document.title = t('settings.documentTitle');
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    const storedToken = window.sessionStorage.getItem(ADMIN_UNLOCK_TOKEN_STORAGE_KEY);
    const rawExpiresAt = window.sessionStorage.getItem(ADMIN_UNLOCK_EXPIRES_AT_STORAGE_KEY);
    const parsedExpiresAt = Number(rawExpiresAt || '0');

    if (!storedToken || !Number.isFinite(parsedExpiresAt) || parsedExpiresAt <= Date.now()) {
      clearAdminUnlockState();
      return;
    }

    setIsAdminUnlocked(true);
    setUnlockExpiresAt(parsedExpiresAt);
    setSystemConfigAdminUnlockToken(storedToken);
  }, [clearAdminUnlockState]);

  useEffect(() => {
    if (!toast) {
      return;
    }

    const timer = window.setTimeout(() => {
      clearToast();
    }, 3200);

    return () => {
      window.clearTimeout(timer);
    };
  }, [clearToast, toast]);

  useEffect(() => {
    if (saveError?.status !== 403) {
      return;
    }

    clearAdminUnlockState();
    setAdminUnlockError(t('settings.adminUnlockExpired'));
  }, [clearAdminUnlockState, saveError?.status, t]);

  const rawActiveItems = itemsByCategory[activeCategory] || [];
  const rawActiveItemMap = new Map(rawActiveItems.map((item) => [item.key, String(item.value ?? '')]));
  const hasConfiguredChannels = Boolean((rawActiveItemMap.get('LLM_CHANNELS') || '').trim());
  const hasLitellmConfig = Boolean((rawActiveItemMap.get('LITELLM_CONFIG') || '').trim());

  const LLM_CHANNEL_KEY_RE = /^LLM_[A-Z0-9]+_(PROTOCOL|BASE_URL|API_KEY|API_KEYS|MODELS|EXTRA_HEADERS|ENABLED)$/;
  const AI_MODEL_HIDDEN_KEYS = new Set([
    'LLM_CHANNELS',
    'LLM_TEMPERATURE',
    'LITELLM_MODEL',
    'AGENT_LITELLM_MODEL',
    'LITELLM_FALLBACK_MODELS',
    'AIHUBMIX_KEY',
    'DEEPSEEK_API_KEY',
    'DEEPSEEK_API_KEYS',
    'GEMINI_API_KEY',
    'GEMINI_API_KEYS',
    'GEMINI_MODEL',
    'GEMINI_MODEL_FALLBACK',
    'GEMINI_TEMPERATURE',
    'ANTHROPIC_API_KEY',
    'ANTHROPIC_API_KEYS',
    'ANTHROPIC_MODEL',
    'ANTHROPIC_TEMPERATURE',
    'ANTHROPIC_MAX_TOKENS',
    'OPENAI_API_KEY',
    'OPENAI_API_KEYS',
    'OPENAI_BASE_URL',
    'OPENAI_MODEL',
    'OPENAI_VISION_MODEL',
    'OPENAI_TEMPERATURE',
    'VISION_MODEL',
  ]);
  const SYSTEM_HIDDEN_KEYS = new Set([
    'ADMIN_AUTH_ENABLED',
  ]);
  const AGENT_HIDDEN_KEYS = new Set([
    'AGENT_DEEP_RESEARCH_BUDGET',
    'AGENT_DEEP_RESEARCH_TIMEOUT',
    'AGENT_EVENT_MONITOR_ENABLED',
    'AGENT_EVENT_MONITOR_INTERVAL_MINUTES',
    'AGENT_EVENT_ALERT_RULES_JSON',
  ]);

  const activeItems =
    activeCategory === 'ai_model'
      ? rawActiveItems.filter((item) => {
        if (hasConfiguredChannels && LLM_CHANNEL_KEY_RE.test(item.key)) {
          return false;
        }
        if (hasConfiguredChannels && !hasLitellmConfig && AI_MODEL_HIDDEN_KEYS.has(item.key)) {
          return false;
        }
        return true;
      })
      : activeCategory === 'system'
        ? rawActiveItems.filter((item) => !SYSTEM_HIDDEN_KEYS.has(item.key))
      : activeCategory === 'agent'
        ? rawActiveItems.filter((item) => !AGENT_HIDDEN_KEYS.has(item.key))
      : rawActiveItems;

  const adminLocked = !isAdminUnlocked;
  const adminSaveDisabled = adminLocked || !hasDirty || isSaving || isLoading;

  const adminUnlockExpiresText = useMemo(() => {
    if (!unlockExpiresAt) {
      return null;
    }
    try {
      return new Date(unlockExpiresAt).toLocaleTimeString(language === 'zh' ? 'zh-CN' : 'en-US', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      });
    } catch {
      return null;
    }
  }, [language, unlockExpiresAt]);

  const handleUnlockSubmit = useCallback(async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setAdminUnlockError(null);

    if (!adminPassword.trim()) {
      setAdminUnlockError(t('settings.adminPasswordRequired'));
      return;
    }

    if (requiresInitialPasswordConfirm && adminPassword.trim() !== adminPasswordConfirm.trim()) {
      setAdminUnlockError(t('settings.adminPasswordConfirmMismatch'));
      return;
    }

    setIsUnlocking(true);
    try {
      const payload = await authApi.verifyAdminPassword(
        adminPassword.trim(),
        requiresInitialPasswordConfirm ? adminPasswordConfirm.trim() : undefined,
      );

      const expiresAt = Date.now() + Math.max(60, payload.expiresInSeconds) * 1000;
      setSystemConfigAdminUnlockToken(payload.unlockToken);
      setIsAdminUnlocked(true);
      setUnlockExpiresAt(expiresAt);
      setAdminPassword('');
      setAdminPasswordConfirm('');

      if (typeof window !== 'undefined') {
        window.sessionStorage.setItem(ADMIN_UNLOCK_TOKEN_STORAGE_KEY, payload.unlockToken);
        window.sessionStorage.setItem(ADMIN_UNLOCK_EXPIRES_AT_STORAGE_KEY, String(expiresAt));
      }
    } catch (error: unknown) {
      const parsed = getParsedApiError(error);
      setAdminUnlockError(parsed.message || t('settings.adminUnlockErrorGeneric'));
    } finally {
      setIsUnlocking(false);
    }
  }, [
    adminPassword,
    adminPasswordConfirm,
    requiresInitialPasswordConfirm,
    t,
  ]);

  const handleSave = useCallback(() => {
    if (adminLocked) {
      setAdminUnlockError(t('settings.adminSaveLocked'));
      return;
    }
    void save();
  }, [adminLocked, save, t]);

  return (
    <div className="workspace-page">
      <div className="workspace-header-panel shadow-soft-card-strong">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-muted-text">{t('settings.eyebrow')}</p>
          <h1 className="mt-2 text-xl font-semibold tracking-tight text-foreground">{t('settings.title')}</h1>
          <p className="mt-2 text-sm leading-6 text-muted-text">
            {t('settings.subtitle')}
          </p>
        </div>
      </div>

      <SettingsSectionCard
        title={t('settings.basicTitle')}
        description={t('settings.basicDesc')}
      >
        <div className="grid gap-4 xl:grid-cols-2">
          <div className="settings-surface rounded-[1rem] border settings-border px-4 py-4">
            <p className="text-sm font-semibold text-foreground">{t('settings.languageTitle')}</p>
            <p className="mt-1 text-xs leading-5 text-muted-text">{t('settings.languageDesc')}</p>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setLanguage('zh')}
                className={language === 'zh'
                  ? 'rounded-lg border border-[var(--border-strong)] bg-[var(--pill-active-bg)] px-3 py-2 text-sm text-foreground shadow-[var(--glow-soft)]'
                  : 'rounded-lg border border-[var(--border-muted)] bg-[var(--pill-bg)] px-3 py-2 text-sm text-secondary-text hover:border-[var(--border-strong)] hover:text-foreground'}
                aria-pressed={language === 'zh'}
              >
                {t('language.zh')}
              </button>
              <button
                type="button"
                onClick={() => setLanguage('en')}
                className={language === 'en'
                  ? 'rounded-lg border border-[var(--border-strong)] bg-[var(--pill-active-bg)] px-3 py-2 text-sm text-foreground shadow-[var(--glow-soft)]'
                  : 'rounded-lg border border-[var(--border-muted)] bg-[var(--pill-bg)] px-3 py-2 text-sm text-secondary-text hover:border-[var(--border-strong)] hover:text-foreground'}
                aria-pressed={language === 'en'}
              >
                {t('language.en')}
              </button>
            </div>
          </div>

          <div className="settings-surface rounded-[1rem] border settings-border px-4 py-4">
            <p className="text-sm font-semibold text-foreground">{t('settings.themeTitle')}</p>
            <p className="mt-1 text-xs leading-5 text-muted-text">{t('settings.themeDesc')}</p>
            <div className="mt-3 space-y-2">
              {THEME_OPTIONS.map((option) => {
                const active = themeStyle === option.value;
                return (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setThemeStyle(option.value)}
                    className={active
                      ? 'w-full rounded-xl border border-[var(--border-strong)] bg-[var(--pill-active-bg)] px-3 py-2 text-left shadow-[var(--glow-soft)]'
                      : 'w-full rounded-xl border border-[var(--border-muted)] bg-[var(--pill-bg)] px-3 py-2 text-left hover:border-[var(--border-strong)]'}
                    aria-pressed={active}
                  >
                    <p className="text-sm font-medium text-foreground">{t(option.labelKey)}</p>
                    <p className="mt-1 text-xs text-muted-text">{t(option.descriptionKey)}</p>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        <FontSizeSettingsCard />
      </SettingsSectionCard>

      <SettingsSectionCard
        title={t('settings.adminTitle')}
        description={t('settings.adminDesc')}
        actions={(
          <div className="flex items-center gap-2">
            <span className={isAdminUnlocked
              ? 'rounded-full border border-[hsl(var(--accent-positive-hsl)/0.48)] bg-[hsl(var(--accent-positive-hsl)/0.18)] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-[hsl(var(--accent-positive-hsl))]'
              : 'rounded-full border border-[hsl(var(--accent-warning-hsl)/0.48)] bg-[hsl(var(--accent-warning-hsl)/0.18)] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-[hsl(var(--accent-warning-hsl))]'}
            >
              {isAdminUnlocked ? t('settings.adminUnlocked') : t('settings.adminLocked')}
            </span>
            {isAdminUnlocked ? (
              <Button
                type="button"
                size="sm"
                variant="settings-secondary"
                onClick={relockAdminSettings}
              >
                {t('settings.adminRelock')}
              </Button>
            ) : null}
          </div>
        )}
      >
        <form className="space-y-3" onSubmit={handleUnlockSubmit}>
          <Input
            type="password"
            allowTogglePassword
            iconType="password"
            label={t('settings.adminPassword')}
            placeholder={t('settings.adminPasswordPlaceholder')}
            value={adminPassword}
            onChange={(event) => setAdminPassword(event.target.value)}
            autoComplete={requiresInitialPasswordConfirm ? 'new-password' : 'current-password'}
            disabled={isUnlocking || isAdminUnlocked}
          />
          {requiresInitialPasswordConfirm ? (
            <Input
              type="password"
              allowTogglePassword
              iconType="password"
              label={t('settings.adminPasswordConfirm')}
              placeholder={t('settings.adminPasswordConfirmPlaceholder')}
              value={adminPasswordConfirm}
              onChange={(event) => setAdminPasswordConfirm(event.target.value)}
              autoComplete="new-password"
              disabled={isUnlocking || isAdminUnlocked}
            />
          ) : null}

          <div className="flex flex-wrap items-center gap-2">
            {!isAdminUnlocked ? (
              <Button
                type="submit"
                variant="settings-primary"
                disabled={isUnlocking}
                isLoading={isUnlocking}
                loadingText={t('settings.adminUnlocking')}
              >
                {t('settings.adminUnlock')}
              </Button>
            ) : null}
            {isAdminUnlocked ? (
              <p className="text-xs text-secondary-text">
                {adminUnlockExpiresText
                  ? t('settings.adminUnlockHint', { time: adminUnlockExpiresText })
                  : t('settings.adminUnlockHintNoTime')}
              </p>
            ) : (
              <p className="text-xs text-muted-text">{t('settings.adminLockedHint')}</p>
            )}
          </div>

          {adminUnlockError ? (
            <SettingsAlert
              title={t('settings.adminUnlockErrorTitle')}
              message={adminUnlockError}
              variant="error"
            />
          ) : null}
        </form>
      </SettingsSectionCard>

      {loadError ? (
        <ApiErrorAlert
          error={loadError}
          actionLabel={retryAction === 'load' ? t('settings.retryLoad') : t('settings.reload')}
          onAction={() => void retry()}
          className="mb-4"
        />
      ) : null}

      {isLoading ? (
        <SettingsLoading />
      ) : (
        <div className="workspace-split-layout">
          <aside className="workspace-split-rail">
            <SettingsCategoryNav
              categories={categories}
              itemsByCategory={itemsByCategory}
              activeCategory={activeCategory}
              onSelect={setActiveCategory}
              disabled={adminLocked}
            />
          </aside>

          <section className="workspace-split-main space-y-4">
            <div className="workspace-surface-muted flex flex-wrap items-center justify-between gap-3 px-4 py-3">
              <p className="text-xs text-secondary-text">
                {adminLocked ? t('settings.adminSaveLocked') : t('settings.adminSaveReady')}
              </p>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="settings-secondary"
                  className="border-border/50 bg-muted/30 hover:border-border/70"
                  onClick={resetDraft}
                  disabled={isLoading || isSaving || adminLocked}
                >
                  {t('settings.reset')}
                </Button>
                <Button
                  type="button"
                  variant="settings-primary"
                  onClick={handleSave}
                  disabled={adminSaveDisabled}
                  isLoading={isSaving}
                  loadingText={t('settings.saving')}
                >
                  {isSaving ? t('settings.saving') : `${t('settings.save')}${dirtyCount ? ` (${dirtyCount})` : ''}`}
                </Button>
              </div>
            </div>

            {saveError ? (
              <ApiErrorAlert
                className="mt-4"
                error={saveError}
                actionLabel={retryAction === 'save' ? t('settings.retrySave') : undefined}
                onAction={retryAction === 'save' ? () => void retry() : undefined}
              />
            ) : null}

            {activeCategory === 'system' && isAdminUnlocked ? <AuthSettingsCard /> : null}
            {activeCategory === 'base' ? (
              <SettingsSectionCard
                title={t('settings.importTitle')}
                description={t('settings.importDesc')}
              >
                <IntelligentImport
                  stockListValue={
                    (activeItems.find((i) => i.key === 'STOCK_LIST')?.value as string) ?? ''
                  }
                  configVersion={configVersion}
                  maskToken={maskToken}
                  onMerged={async () => {
                    if (adminLocked) {
                      return;
                    }
                    await refreshAfterExternalSave(['STOCK_LIST']);
                  }}
                  disabled={isSaving || isLoading || adminLocked}
                />
              </SettingsSectionCard>
            ) : null}
            {activeCategory === 'ai_model' ? (
              <SettingsSectionCard
                title={t('settings.llmTitle')}
                description={t('settings.llmDesc')}
              >
                <LLMChannelEditor
                  items={rawActiveItems}
                  configVersion={configVersion}
                  maskToken={maskToken}
                  onSaved={async (updatedItems) => {
                    if (adminLocked) {
                      return;
                    }
                    await refreshAfterExternalSave(updatedItems.map((item) => item.key));
                  }}
                  disabled={isSaving || isLoading || adminLocked}
                />
              </SettingsSectionCard>
            ) : null}
            {activeCategory === 'system' && passwordChangeable && isAdminUnlocked ? (
              <ChangePasswordCard />
            ) : null}

            {activeItems.length ? (
              <SettingsSectionCard
                title={t('settings.currentCategory')}
                description={getCategoryDescription(language, activeCategory as SystemConfigCategory, '') || t('settings.currentCategoryDesc')}
              >
                {activeItems.map((item) => (
                  <SettingsField
                    key={item.key}
                    item={item}
                    value={item.value}
                    disabled={isSaving || adminLocked}
                    onChange={(key, value) => {
                      if (adminLocked) {
                        return;
                      }
                      setDraftValue(key, value);
                    }}
                    issues={issueByKey[item.key] || []}
                  />
                ))}
              </SettingsSectionCard>
            ) : (
              <div className="settings-panel-muted rounded-[1.5rem] border p-5 text-sm text-secondary-text shadow-soft-card">
                {t('settings.noItems')}
              </div>
            )}
          </section>
        </div>
      )}

      {toast ? (
        <div className="fixed bottom-5 right-5 z-50 w-[320px] max-w-[calc(100vw-24px)]">
          {toast.type === 'success'
            ? <SettingsAlert title={t('settings.success')} message={toast.message} variant="success" />
            : <ApiErrorAlert error={toast.error} />}
        </div>
      ) : null}
    </div>
  );
};

export default SettingsPage;
