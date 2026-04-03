import type React from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { authApi } from '../api/auth';
import { getParsedApiError } from '../api/error';
import { SystemConfigValidationError } from '../api/systemConfig';
import { ApiErrorAlert, Button, Input, Select, WorkspacePageHeader } from '../components/common';
import { useThemeStyle, type ThemeStylePreset } from '../components/theme/ThemeProvider';
import { useI18n } from '../contexts/UiLanguageContext';
import { useAuth, useSystemConfig } from '../hooks';
import type { SystemConfigCategory } from '../types/systemConfig';
import {
  GATEWAY_READINESS_NOTES,
  getGatewayModelOptions,
  isGatewayModelCompatible,
  KNOWN_GATEWAY_MODEL_PRESETS,
  parseGatewayFromModel as parseGatewayFromModelId,
  supportsCustomModelId,
} from '../utils/aiRouting';
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

type SettingsDomain = 'ai_models' | 'data_sources' | 'notifications' | 'advanced';
type RoutingTier = 'primary' | 'backup' | 'fallback';
type ModelInputMode = 'preset' | 'custom';
type AiRoutingScope = 'analysis' | 'ask_stock' | 'both';

type RoutingDraftState = {
  ai: {
    primaryChannel: string;
    backupChannel: string;
    primaryModel: string;
    backupModel: string;
  };
  market: {
    primary: string;
    backup: string;
    fallback: string;
  };
  fundamentals: {
    primary: string;
    backup: string;
    fallback: string;
  };
  news: {
    primary: string;
    backup: string;
  };
  sentiment: {
    primary: string;
    backup: string;
  };
  notification: {
    primary: string;
    backup: string;
  };
};

const DOMAIN_ORDER: SettingsDomain[] = ['ai_models', 'data_sources', 'notifications', 'advanced'];

const CATEGORY_TO_DOMAIN: Partial<Record<SystemConfigCategory, SettingsDomain>> = {
  ai_model: 'ai_models',
  data_source: 'data_sources',
  notification: 'notifications',
  system: 'advanced',
  agent: 'advanced',
  backtest: 'advanced',
  base: 'advanced',
  uncategorized: 'advanced',
};

const FALSE_VALUES = new Set(['', '0', 'false', 'no', 'off']);

const splitCsv = (value?: string): string[] => (value || '')
  .split(',')
  .map((entry) => entry.trim())
  .filter(Boolean);

const uniqueValues = (values: Array<string | null | undefined>): string[] => {
  const seen = new Set<string>();
  const list: string[] = [];
  values.forEach((value) => {
    const normalized = String(value || '').trim();
    if (!normalized || seen.has(normalized)) {
      return;
    }
    seen.add(normalized);
    list.push(normalized);
  });
  return list;
};

const hasConfigValue = (value: string): boolean => String(value || '').trim().length > 0;
const isEnabledValue = (value: string | undefined): boolean => {
  const normalized = String(value || '').trim().toLowerCase();
  if (!normalized) return false;
  return !FALSE_VALUES.has(normalized);
};
const normalizeGatewayKey = (value: string): string => String(value || '').trim().toLowerCase();
const parseGatewayFromModel = (value: string): string => parseGatewayFromModelId(value);

const normalizeLabel = (value: string): string => value
  .replace(/[_-]+/g, ' ')
  .replace(/\s+/g, ' ')
  .trim();

const titleCase = (value: string): string => normalizeLabel(value)
  .split(' ')
  .map((segment) => segment ? `${segment[0].toUpperCase()}${segment.slice(1).toLowerCase()}` : segment)
  .join(' ');

const prettySourceLabel = (value: string): string => {
  const normalized = normalizeLabel(value);
  if (!normalized) return '';
  if (/^[A-Z0-9_-]{2,}$/.test(normalized)) {
    return normalized;
  }
  return titleCase(normalized);
};

const parseNotificationChannel = (key: string): string => key
  .replace(/_(ENABLED|SWITCH|TOGGLE)$/i, '')
  .replace(/_(WEBHOOK|URL|TOKEN|CHAT_ID|EMAIL)$/i, '')
  .trim();

const sourceToneClass = (index: number): string => {
  if (index === 0) return 'text-[var(--accent-primary)]';
  if (index === 1) return 'text-[var(--accent-positive)]';
  if (index === 2) return 'text-[var(--accent-warning)]';
  return 'text-muted-text';
};

const findFirstKey = (keys: string[], patterns: RegExp[], fallbackKey: string): string => {
  const matched = keys.find((key) => patterns.some((pattern) => pattern.test(key)));
  return matched || fallbackKey;
};

const toRouteState = (values: string[], allowThird = true) => ({
  primary: values[0] || '',
  backup: values[1] || '',
  fallback: allowThird ? (values[2] || '') : '',
});

const AI_PROVIDER_CREDENTIAL_RULES: Array<{ gateway: string; patterns: RegExp[] }> = [
  {
    gateway: 'aihubmix',
    patterns: [/^AIHUBMIX_KEY$/i, /^AIHUBMIX_KEYS$/i, /^LLM_AIHUBMIX_API_KEYS?$/i],
  },
  {
    gateway: 'gemini',
    patterns: [/^GEMINI_API_KEYS?$/i, /^LLM_GEMINI_API_KEYS?$/i],
  },
  {
    gateway: 'openai',
    patterns: [/^OPENAI_API_KEYS?$/i, /^LLM_OPENAI_API_KEYS?$/i],
  },
  {
    gateway: 'deepseek',
    patterns: [/^DEEPSEEK_API_KEYS?$/i, /^LLM_DEEPSEEK_API_KEYS?$/i],
  },
  {
    gateway: 'anthropic',
    patterns: [/^ANTHROPIC_API_KEYS?$/i, /^LLM_ANTHROPIC_API_KEYS?$/i],
  },
];

const credentialEntryCount = (value: string, rawValueExists: boolean): number => {
  const normalized = String(value || '').trim();
  if (normalized) {
    return splitCsv(normalized).length || 1;
  }
  return rawValueExists ? 1 : 0;
};

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
    saveExternalItems,
    resetDraft,
    setDraftValue,
    adminUnlockToken,
    adminUnlockExpiresAt,
    isAdminUnlocked,
    setAdminUnlockSession,
    clearAdminUnlockSession,
  } = useSystemConfig();
  const [activeDomain, setActiveDomain] = useState<SettingsDomain>('advanced');

  const clearAdminUnlockState = useCallback(() => {
    setAdminPassword('');
    setAdminPasswordConfirm('');
    clearAdminUnlockSession();
  }, [clearAdminUnlockSession]);

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
  const allItems = useMemo(() => Object.values(itemsByCategory).flat(), [itemsByCategory]);
  const allItemMap = useMemo(
    () => new Map(allItems.map((item) => [item.key, String(item.value ?? '')])),
    [allItems],
  );
  const categoryDomainMap = useMemo(() => {
    const map = new Map<string, SettingsDomain>();
    categories.forEach((category) => {
      map.set(
        category.category,
        CATEGORY_TO_DOMAIN[category.category as SystemConfigCategory] || 'advanced',
      );
    });
    return map;
  }, [categories]);
  const domainCategories = useMemo(
    () => categories.filter((category) => (categoryDomainMap.get(category.category) || 'advanced') === activeDomain),
    [activeDomain, categories, categoryDomainMap],
  );
  const domainCategorySet = useMemo(
    () => new Set(domainCategories.map((category) => category.category)),
    [domainCategories],
  );
  const hasConfiguredChannels = Boolean((rawActiveItemMap.get('LLM_CHANNELS') || '').trim());
  const hasLitellmConfig = Boolean((rawActiveItemMap.get('LITELLM_CONFIG') || '').trim());

  const LLM_CHANNEL_KEY_RE = /^LLM_[A-Z0-9]+_(PROTOCOL|BASE_URL|API_KEY|API_KEYS|MODELS|EXTRA_HEADERS|ENABLED)$/;
  const AI_MODEL_HIDDEN_KEYS = new Set([
    'AI_PRIMARY_GATEWAY',
    'AI_PRIMARY_MODEL',
    'AI_BACKUP_GATEWAY',
    'AI_BACKUP_MODEL',
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
    'SHOW_RUNTIME_EXECUTION_SUMMARY',
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

  useEffect(() => {
    const inferredDomain = categoryDomainMap.get(activeCategory) || 'advanced';
    setActiveDomain((previous) => (previous === inferredDomain ? previous : inferredDomain));
  }, [activeCategory, categoryDomainMap]);

  useEffect(() => {
    if (domainCategorySet.size === 0) {
      return;
    }
    if (domainCategorySet.has(activeCategory as SystemConfigCategory)) {
      return;
    }
    const firstCategory = domainCategories[0]?.category;
    if (firstCategory) {
      setActiveCategory(firstCategory);
    }
  }, [activeCategory, domainCategories, domainCategorySet, setActiveCategory]);

  const domainNavItems = useMemo(() => ([
    {
      domain: 'ai_models' as const,
      title: t('settings.domainAiTitle'),
      desc: t('settings.domainAiDesc'),
    },
    {
      domain: 'data_sources' as const,
      title: t('settings.domainDataTitle'),
      desc: t('settings.domainDataDesc'),
    },
    {
      domain: 'notifications' as const,
      title: t('settings.domainNotificationTitle'),
      desc: t('settings.domainNotificationDesc'),
    },
    {
      domain: 'advanced' as const,
      title: t('settings.domainAdvancedTitle'),
      desc: t('settings.domainAdvancedDesc'),
    },
  ]), [t]);

  const aiRoutingKeys = useMemo(() => {
    const keys = [...allItemMap.keys()];
    return {
      primaryGateway: findFirstKey(keys, [/^AI_PRIMARY_GATEWAY$/i], 'AI_PRIMARY_GATEWAY'),
      primaryModel: findFirstKey(keys, [/^AI_PRIMARY_MODEL$/i], 'AI_PRIMARY_MODEL'),
      backupGateway: findFirstKey(keys, [/^AI_BACKUP_GATEWAY$/i], 'AI_BACKUP_GATEWAY'),
      backupModel: findFirstKey(keys, [/^AI_BACKUP_MODEL$/i], 'AI_BACKUP_MODEL'),
    };
  }, [allItemMap]);

  const aiGatewayModelMap = useMemo(() => {
    const map = new Map<string, string[]>();
    for (const [key, value] of allItemMap.entries()) {
      const matched = key.match(/^LLM_([A-Z0-9]+)_MODELS$/i);
      if (!matched) continue;
      const gateway = normalizeGatewayKey(matched[1] || '');
      const models = splitCsv(value);
      if (!gateway || !models.length) continue;
      map.set(gateway, uniqueValues([...(map.get(gateway) || []), ...models]));
    }
    return map;
  }, [allItemMap]);

  const aiCredentialProviders = useMemo(() => {
    const counts = new Map<string, number>();
    const addProviderCount = (gateway: string, count: number) => {
      const normalizedGateway = normalizeGatewayKey(gateway);
      if (!normalizedGateway || count <= 0) return;
      counts.set(normalizedGateway, (counts.get(normalizedGateway) || 0) + count);
    };

    allItems.forEach((item) => {
      const key = item.key;
      let matchedGateway = '';
      const explicitRule = AI_PROVIDER_CREDENTIAL_RULES.find((rule) => rule.patterns.some((pattern) => pattern.test(key)));
      if (explicitRule) {
        matchedGateway = explicitRule.gateway;
      } else {
        const legacyMatch = key.match(/^LLM_([A-Z0-9]+)_API_KEYS?$/i);
        if (legacyMatch) {
          matchedGateway = normalizeGatewayKey(legacyMatch[1] || '');
        }
      }
      if (!matchedGateway) return;
      const count = credentialEntryCount(String(item.value || ''), Boolean(item.rawValueExists));
      if (count <= 0) return;
      addProviderCount(matchedGateway, count);
    });

    // Route editor availability should be derived from credential readiness only.
    // Do not depend on legacy LLM_CHANNELS, which is channel-editor-owned.
    const configuredChannels = [...counts.keys()];

    return {
      configuredProviderMap: counts,
      configuredProviders: [...counts.entries()],
      configuredChannels,
      configuredCount: [...counts.values()].reduce((total, count) => total + count, 0),
    };
  }, [allItems]);

  const aiSummary = useMemo(() => {
    const primaryModelLegacy = allItemMap.get('LITELLM_MODEL') || '';
    const fallbackModelsLegacy = splitCsv(allItemMap.get('LITELLM_FALLBACK_MODELS'));
    const channelsLegacy = splitCsv(allItemMap.get('LLM_CHANNELS'));

    const primaryChannel = allItemMap.get(aiRoutingKeys.primaryGateway) || channelsLegacy[0] || '';
    const backupChannel = allItemMap.get(aiRoutingKeys.backupGateway) || channelsLegacy[1] || '';
    const primaryModel = allItemMap.get(aiRoutingKeys.primaryModel) || primaryModelLegacy || '';
    const backupModel = allItemMap.get(aiRoutingKeys.backupModel) || fallbackModelsLegacy[0] || '';
    const provider = parseGatewayFromModel(primaryModel);
    const configuredApiCount = aiCredentialProviders.configuredCount;
    const hasPrimaryRoute = Boolean(primaryChannel && primaryModel);
    const hasBackupRoute = Boolean(backupChannel && backupModel);
    const routeConfigured = hasPrimaryRoute && hasBackupRoute;
    const routeMissingButApiConfigured = !routeConfigured && configuredApiCount > 0;
    const routeStatus: 'fully_configured' | 'partially_configured' | 'credentials_only' | 'not_configured' =
      routeConfigured
        ? 'fully_configured'
        : (hasPrimaryRoute || hasBackupRoute)
          ? 'partially_configured'
          : routeMissingButApiConfigured
            ? 'credentials_only'
            : 'not_configured';

    return {
      primaryModel,
      provider,
      primaryChannel,
      backupChannel,
      backupModel,
      fallbackModels: uniqueValues([backupModel, ...fallbackModelsLegacy]),
      modelRoute: [primaryModel, backupModel, ...fallbackModelsLegacy].filter(Boolean),
      configuredProviders: aiCredentialProviders.configuredProviders,
      configuredApiCount,
      hasPrimaryRoute,
      hasBackupRoute,
      routeConfigured,
      routeMissingButApiConfigured,
      routeStatus,
    };
  }, [aiCredentialProviders.configuredCount, aiCredentialProviders.configuredProviders, aiRoutingKeys.backupGateway, aiRoutingKeys.backupModel, aiRoutingKeys.primaryGateway, aiRoutingKeys.primaryModel, allItemMap]);

  const dataPriorityKeys = useMemo(() => {
    const keys = [...allItemMap.keys()];
    return {
      market: findFirstKey(keys, [/^REALTIME_SOURCE_PRIORITY$/i, /MARKET.*PRIORITY/i], 'REALTIME_SOURCE_PRIORITY'),
      fundamentals: findFirstKey(keys, [/(FUNDAMENTAL|FINANCIAL|EARNINGS).*PRIORITY/i], 'FUNDAMENTAL_SOURCE_PRIORITY'),
      news: findFirstKey(keys, [/NEWS.*PRIORITY/i], 'NEWS_SOURCE_PRIORITY'),
      sentiment: findFirstKey(keys, [/SENTIMENT.*PRIORITY/i], 'SENTIMENT_SOURCE_PRIORITY'),
      notification: findFirstKey(keys, [/NOTIFICATION.*PRIORITY/i, /CHANNEL.*PRIORITY/i], 'NOTIFICATION_CHANNEL_PRIORITY'),
    };
  }, [allItemMap]);
  const runtimeSummaryVisibilityKey = useMemo(() => {
    const keys = [...allItemMap.keys()];
    return findFirstKey(keys, [/^SHOW_RUNTIME_EXECUTION_SUMMARY$/i], 'SHOW_RUNTIME_EXECUTION_SUMMARY');
  }, [allItemMap]);

  const dataSummary = useMemo(() => {
    const market = allItemMap.get(dataPriorityKeys.market) || '';
    const fundamentals = allItemMap.get(dataPriorityKeys.fundamentals) || '';
    const news = allItemMap.get(dataPriorityKeys.news) || '';
    const sentiment = allItemMap.get(dataPriorityKeys.sentiment) || '';
    const sharedNewsSentiment = [...allItemMap.entries()].find(([key, value]) => {
      return value.trim().length > 0 && /(NEWS|SENTIMENT).*PRIORITY/i.test(key);
    })?.[1] || '';

    return {
      market: splitCsv(market),
      fundamentals: splitCsv(fundamentals),
      news: splitCsv(news || sharedNewsSentiment),
      sentiment: splitCsv(sentiment || sharedNewsSentiment),
    };
  }, [allItemMap, dataPriorityKeys]);

  const notificationSummary = useMemo(() => {
    const notificationItems = itemsByCategory.notification || [];
    const configuredChannels: string[] = [];
    const enabledChannels: string[] = [];
    const destinations: string[] = [];

    notificationItems.forEach((item) => {
      const value = String(item.value || '').trim();
      if (!value) {
        return;
      }
      const channel = parseNotificationChannel(item.key);
      if (channel) {
        configuredChannels.push(channel.toLowerCase());
      }
      if (/ENABLED|SWITCH|TOGGLE/i.test(item.key) && !FALSE_VALUES.has(value.toLowerCase())) {
        if (channel) {
          enabledChannels.push(channel.toLowerCase());
        }
      }
      if (/(WEBHOOK|EMAIL|TOKEN|CHAT|DINGTALK|DISCORD|WECHAT|PUSHPLUS)/i.test(item.key)) {
        destinations.push(item.key);
      }
    });

    return {
      configuredChannels: [...new Set(configuredChannels)],
      enabledChannels: [...new Set(enabledChannels)],
      destinations,
    };
  }, [itemsByCategory.notification]);
  const notificationRoute = useMemo(() => {
    const explicit = splitCsv(allItemMap.get(dataPriorityKeys.notification));
    if (explicit.length) {
      return explicit;
    }
    return notificationSummary.enabledChannels.length
      ? notificationSummary.enabledChannels
      : notificationSummary.configuredChannels;
  }, [allItemMap, dataPriorityKeys.notification, notificationSummary.configuredChannels, notificationSummary.enabledChannels]);

  const availableProviders = useMemo(() => {
    const hasAny = (...keys: string[]): boolean => keys.some((key) => hasConfigValue(allItemMap.get(key) || ''));
    const hasByPattern = (patterns: RegExp[]): boolean => {
      for (const [key, value] of allItemMap.entries()) {
        if (!hasConfigValue(value)) continue;
        if (patterns.some((pattern) => pattern.test(key))) return true;
      }
      return false;
    };

    const aiChannels = uniqueValues([
      aiSummary.primaryChannel,
      aiSummary.backupChannel,
      ...aiCredentialProviders.configuredChannels,
    ]);

    const modelSet = new Set<string>();
    splitCsv(allItemMap.get('LITELLM_MODEL')).forEach((model) => modelSet.add(model));
    splitCsv(allItemMap.get('LITELLM_FALLBACK_MODELS')).forEach((model) => modelSet.add(model));
    [...allItemMap.entries()].forEach(([key, value]) => {
      if (!/LLM_[A-Z0-9]+_MODELS$/i.test(key)) return;
      splitCsv(value).forEach((model) => modelSet.add(model));
    });
    if (aiSummary.primaryModel) modelSet.add(aiSummary.primaryModel);
    if (aiSummary.backupModel) modelSet.add(aiSummary.backupModel);

    const market = uniqueValues([
      hasByPattern([/^ALPHA_VANTAGE_API_KEYS?$/i, /^ALPHAVANTAGE_API_KEYS?$/i]) ? 'alpha_vantage' : '',
      hasByPattern([/^FINNHUB_API_KEYS?$/i]) ? 'finnhub' : '',
      'yahoo',
    ]);
    const fundamentals = uniqueValues([
      hasByPattern([/^FMP_API_KEYS?$/i]) ? 'fmp' : '',
      hasByPattern([/^FINNHUB_API_KEYS?$/i]) ? 'finnhub' : '',
      'yahoo',
    ]);
    const news = uniqueValues([
      hasByPattern([/^GNEWS_API_KEYS?$/i]) ? 'gnews' : '',
      hasByPattern([/^TAVILY_API_KEYS?$/i]) ? 'tavily' : '',
      hasByPattern([/^FINNHUB_API_KEYS?$/i]) ? 'finnhub' : '',
    ]);
    const sentiment = uniqueValues([
      hasAny('SOCIAL_SENTIMENT_API_KEY', 'SOCIAL_SENTIMENT_API_KEYS') ? 'social_sentiment_service' : '',
      hasByPattern([/^TAVILY_API_KEYS?$/i]) ? 'tavily' : '',
      'local_inference',
    ]);

    return {
      aiChannels,
      aiModels: [...modelSet].filter(Boolean),
      market,
      fundamentals,
      news,
      sentiment,
      notifications: notificationSummary.configuredChannels,
    };
  }, [aiCredentialProviders.configuredChannels, aiSummary.backupChannel, aiSummary.backupModel, aiSummary.primaryChannel, aiSummary.primaryModel, allItemMap, notificationSummary.configuredChannels]);

  const aiSavedModels = useMemo(
    () => uniqueValues([
      aiSummary.primaryModel,
      aiSummary.backupModel,
      ...aiSummary.fallbackModels,
      ...splitCsv(allItemMap.get('LITELLM_MODEL')),
      ...splitCsv(allItemMap.get('LITELLM_FALLBACK_MODELS')),
    ]),
    [aiSummary.backupModel, aiSummary.fallbackModels, aiSummary.primaryModel, allItemMap],
  );

  const [routingDraft, setRoutingDraft] = useState<RoutingDraftState>({
    ai: { primaryChannel: '', backupChannel: '', primaryModel: '', backupModel: '' },
    market: { primary: '', backup: '', fallback: '' },
    fundamentals: { primary: '', backup: '', fallback: '' },
    news: { primary: '', backup: '' },
    sentiment: { primary: '', backup: '' },
    notification: { primary: '', backup: '' },
  });
  const [aiModelMode, setAiModelMode] = useState<{ primary: ModelInputMode; backup: ModelInputMode }>({
    primary: 'preset',
    backup: 'preset',
  });
  const [aiRoutingError, setAiRoutingError] = useState<string | null>(null);
  const [showRuntimeExecutionSummary, setShowRuntimeExecutionSummary] = useState(false);

  useEffect(() => {
    const primaryChannel = aiSummary.primaryChannel || '';
    const backupChannel = aiSummary.backupChannel || '';
    const primaryModel = primaryChannel ? (aiSummary.primaryModel || '') : '';
    const backupModel = backupChannel ? (aiSummary.backupModel || '') : '';

    const primaryModelOptions = getGatewayModelOptions(
      primaryChannel,
      aiGatewayModelMap,
      availableProviders.aiModels,
      aiSavedModels,
    );
    const backupModelOptions = getGatewayModelOptions(
      backupChannel,
      aiGatewayModelMap,
      availableProviders.aiModels,
      aiSavedModels,
    );

    setRoutingDraft({
      ai: {
        primaryChannel,
        backupChannel,
        primaryModel,
        backupModel,
      },
      market: toRouteState(dataSummary.market, true),
      fundamentals: toRouteState(dataSummary.fundamentals, true),
      news: {
        primary: dataSummary.news[0] || '',
        backup: dataSummary.news[1] || '',
      },
      sentiment: {
        primary: dataSummary.sentiment[0] || '',
        backup: dataSummary.sentiment[1] || '',
      },
      notification: {
        primary: notificationRoute[0] || '',
        backup: notificationRoute[1] || '',
      },
    });
    setAiModelMode({
      primary: primaryChannel && primaryModel && !primaryModelOptions.includes(primaryModel) ? 'custom' : 'preset',
      backup: backupChannel && backupModel && !backupModelOptions.includes(backupModel) ? 'custom' : 'preset',
    });
  }, [
    aiGatewayModelMap,
    aiSavedModels,
    aiSummary.backupChannel,
    aiSummary.backupModel,
    aiSummary.primaryChannel,
    aiSummary.primaryModel,
    availableProviders.aiModels,
    dataSummary.fundamentals,
    dataSummary.market,
    dataSummary.news,
    dataSummary.sentiment,
    notificationRoute,
  ]);
  useEffect(() => {
    setShowRuntimeExecutionSummary(isEnabledValue(allItemMap.get(runtimeSummaryVisibilityKey)));
  }, [allItemMap, runtimeSummaryVisibilityKey]);

  const adminLocked = !isAdminUnlocked;
  const adminSaveDisabled = adminLocked || !hasDirty || isSaving || isLoading;

  const adminUnlockExpiresText = useMemo(() => {
    if (!adminUnlockExpiresAt) {
      return null;
    }
    try {
      return new Date(adminUnlockExpiresAt).toLocaleTimeString(language === 'zh' ? 'zh-CN' : 'en-US', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      });
    } catch {
      return null;
    }
  }, [adminUnlockExpiresAt, language]);

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
      setAdminUnlockSession(payload.unlockToken, expiresAt);
      setAdminPassword('');
      setAdminPasswordConfirm('');
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
    setAdminUnlockSession,
    t,
  ]);

  const handleSave = useCallback(() => {
    if (adminLocked) {
      setAdminUnlockError(t('settings.adminSaveLocked'));
      return;
    }
    void save();
  }, [adminLocked, save, t]);

  const priorityLabel = useCallback((index: number): string => {
    if (index === 0) return t('settings.sourcePrimary');
    if (index === 1) return t('settings.sourceBackup');
    if (index === 2) return t('settings.sourceSecondaryBackup');
    return t('settings.sourceFinalFallback');
  }, [t]);

  const setRouteTier = useCallback((
    section: 'market' | 'fundamentals' | 'news' | 'sentiment' | 'notification',
    tier: RoutingTier,
    value: string,
  ) => {
    setRoutingDraft((prev) => {
      if (section === 'news' || section === 'sentiment' || section === 'notification') {
        const current = prev[section];
        if (tier === 'fallback') {
          return prev;
        }
        const next = { ...current, [tier]: value };
        if (tier === 'primary' && next.backup === value) {
          next.backup = '';
        }
        if (tier === 'backup' && next.primary === value) {
          next.primary = '';
        }
        return { ...prev, [section]: next };
      }

      const current = prev[section];
      const next = { ...current, [tier]: value };
      if (tier === 'primary') {
        if (next.backup === value) next.backup = '';
        if (next.fallback === value) next.fallback = '';
      }
      if (tier === 'backup') {
        if (next.primary === value) next.primary = '';
        if (next.fallback === value) next.fallback = '';
      }
      if (tier === 'fallback') {
        if (next.primary === value) next.primary = '';
        if (next.backup === value) next.backup = '';
      }
      return { ...prev, [section]: next };
    });
  }, []);

  const effectiveRoute = useCallback((values: Array<string | undefined | null>): string[] => uniqueValues(values), []);

  const modelsForGateway = useCallback((gateway: string): string[] => (
    getGatewayModelOptions(
      gateway,
      aiGatewayModelMap,
      availableProviders.aiModels,
      aiSavedModels,
    )
  ), [aiGatewayModelMap, availableProviders.aiModels, aiSavedModels]);

  const primaryGatewayModels = useMemo(
    () => modelsForGateway(routingDraft.ai.primaryChannel),
    [modelsForGateway, routingDraft.ai.primaryChannel],
  );

  const backupGatewayModels = useMemo(
    () => modelsForGateway(routingDraft.ai.backupChannel),
    [modelsForGateway, routingDraft.ai.backupChannel],
  );

  const aiGatewayReadiness = useMemo(() => {
    const configuredProviderMap = new Map(aiSummary.configuredProviders);
    const gateways = uniqueValues([
      ...availableProviders.aiChannels,
      ...[...aiGatewayModelMap.keys()],
      ...[...configuredProviderMap.keys()],
      routingDraft.ai.primaryChannel,
      routingDraft.ai.backupChannel,
    ]);
    return gateways.map((gateway) => {
      const normalized = normalizeGatewayKey(gateway);
      const presets = KNOWN_GATEWAY_MODEL_PRESETS[normalized] || [];
      const inferred = aiGatewayModelMap.get(normalized) || [];
      const credentialCount = configuredProviderMap.get(normalized) || 0;
      return {
        gateway: normalized,
        label: prettySourceLabel(normalized),
        credentialCount,
        credentialReady: credentialCount > 0,
        presetCount: presets.length,
        inferredCount: inferred.length,
        supportsCustom: supportsCustomModelId(normalized),
        noteKey: GATEWAY_READINESS_NOTES[normalized] || 'generic',
      };
    });
  }, [
    aiSummary.configuredProviders,
    aiGatewayModelMap,
    availableProviders.aiChannels,
    routingDraft.ai.backupChannel,
    routingDraft.ai.primaryChannel,
  ]);
  const aiCredentialReadyGateways = useMemo(
    () => [...aiCredentialProviders.configuredProviderMap.keys()],
    [aiCredentialProviders.configuredProviderMap],
  );
  const aiGatewaySelectorOptions = useMemo(
    () => uniqueValues([
      ...aiCredentialReadyGateways,
      routingDraft.ai.primaryChannel,
      routingDraft.ai.backupChannel,
    ]).filter(Boolean),
    [aiCredentialReadyGateways, routingDraft.ai.backupChannel, routingDraft.ai.primaryChannel],
  );
  const aiConfiguredGatewayCount = aiCredentialReadyGateways.length;
  const canSelectPrimaryGateway = aiConfiguredGatewayCount >= 1;
  const canSelectBackupGateway = aiConfiguredGatewayCount >= 2;
  const aiSelectorReadinessMismatch = useMemo(() => {
    const readinessHasConfiguredProvider = aiGatewayReadiness.some((provider) => provider.credentialReady);
    return readinessHasConfiguredProvider && aiGatewaySelectorOptions.length === 0;
  }, [aiGatewayReadiness, aiGatewaySelectorOptions.length]);

  useEffect(() => {
    if (!aiSelectorReadinessMismatch) return;
    console.warn('[Settings][AI Routing] readiness reports configured providers but selector options are empty', {
      readinessProviders: aiGatewayReadiness.filter((provider) => provider.credentialReady).map((provider) => provider.gateway),
      configuredChannels: aiCredentialReadyGateways,
      llmChannels: splitCsv(allItemMap.get('LLM_CHANNELS')),
    });
  }, [aiCredentialReadyGateways, aiGatewayReadiness, aiSelectorReadinessMismatch, allItemMap]);

  const primaryGatewayDisabledReason = useMemo(() => {
    if (adminLocked) return t('settings.adminSaveLocked');
    if (isSaving) return t('settings.saving');
    if (!canSelectPrimaryGateway) return t('settings.aiPrimaryGatewayDisabledReason');
    return '';
  }, [adminLocked, canSelectPrimaryGateway, isSaving, t]);

  const backupGatewayDisabledReason = useMemo(() => {
    if (adminLocked) return t('settings.adminSaveLocked');
    if (isSaving) return t('settings.saving');
    if (!canSelectBackupGateway) return t('settings.aiBackupGatewayDisabledReason');
    return '';
  }, [adminLocked, canSelectBackupGateway, isSaving, t]);

  const primaryModelCompatible = useMemo(
    () => isGatewayModelCompatible(routingDraft.ai.primaryChannel, routingDraft.ai.primaryModel, primaryGatewayModels),
    [primaryGatewayModels, routingDraft.ai.primaryChannel, routingDraft.ai.primaryModel],
  );
  const backupModelCompatible = useMemo(
    () => isGatewayModelCompatible(routingDraft.ai.backupChannel, routingDraft.ai.backupModel, backupGatewayModels),
    [backupGatewayModels, routingDraft.ai.backupChannel, routingDraft.ai.backupModel],
  );

  useEffect(() => {
    setRoutingDraft((prev) => {
      const next = { ...prev, ai: { ...prev.ai } };
      let changed = false;

      if (!next.ai.primaryChannel && next.ai.primaryModel) {
        next.ai.primaryModel = '';
        changed = true;
      }
      if (!next.ai.backupChannel && next.ai.backupModel) {
        next.ai.backupModel = '';
        changed = true;
      }

      if (next.ai.primaryChannel && aiModelMode.primary === 'preset') {
        const primaryOptions = primaryGatewayModels;
        if (primaryOptions.length === 0) {
          if (next.ai.primaryModel) {
            next.ai.primaryModel = '';
            changed = true;
          }
        } else if (!primaryOptions.includes(next.ai.primaryModel)) {
          next.ai.primaryModel = primaryOptions[0];
          changed = true;
        }
      }

      if (next.ai.backupChannel && aiModelMode.backup === 'preset') {
        const backupOptions = backupGatewayModels.filter((model) => model !== next.ai.primaryModel);
        if (backupOptions.length === 0) {
          if (next.ai.backupModel) {
            next.ai.backupModel = '';
            changed = true;
          }
        } else if (!backupOptions.includes(next.ai.backupModel)) {
          const candidate = backupOptions[0];
          if (candidate) {
            next.ai.backupModel = candidate;
            changed = true;
          }
        }
      } else if (next.ai.backupModel && next.ai.backupModel === next.ai.primaryModel) {
        if (backupGatewayModels.length > 0) {
          const candidate = backupGatewayModels.find((model) => model !== next.ai.primaryModel);
          next.ai.backupModel = candidate || '';
          changed = true;
        } else {
          next.ai.backupModel = '';
          changed = true;
        }
      }

      if (!changed) {
        return prev;
      }
      return next;
    });
  }, [aiModelMode.backup, aiModelMode.primary, backupGatewayModels, primaryGatewayModels]);

  const aiRoutingScope = useMemo<AiRoutingScope>(() => {
    const agentMode = String(allItemMap.get('AGENT_MODE') || '').trim().toLowerCase();
    const agentDisabled = Boolean(agentMode) && FALSE_VALUES.has(agentMode);
    if (agentDisabled) {
      return 'analysis';
    }
    const hasAgentOverrideModel = Boolean(String(allItemMap.get('AGENT_LITELLM_MODEL') || '').trim());
    const hasAnalysisRoute = Boolean(
      routingDraft.ai.primaryChannel.trim() && routingDraft.ai.primaryModel.trim(),
    );
    if (hasAnalysisRoute && !hasAgentOverrideModel) {
      return 'both';
    }
    if (!hasAnalysisRoute && hasAgentOverrideModel) {
      return 'ask_stock';
    }
    return 'analysis';
  }, [allItemMap, routingDraft.ai.primaryChannel, routingDraft.ai.primaryModel]);

  const formatRouteLine = useCallback((gateway: string, model: string): string => {
    const normalizedGateway = gateway.trim();
    const normalizedModel = model.trim();
    if (!normalizedGateway || !normalizedModel) {
      return t('settings.notConfigured');
    }
    return `${prettySourceLabel(normalizedGateway)} / ${normalizedModel}`;
  }, [t]);

  const saveAiRouting = useCallback(async () => {
    if (adminLocked) {
      setAdminUnlockError(t('settings.adminSaveLocked'));
      return;
    }
    setAiRoutingError(null);
    const primaryGateway = routingDraft.ai.primaryChannel.trim();
    const backupGateway = routingDraft.ai.backupChannel.trim();
    const primaryModel = primaryGateway ? routingDraft.ai.primaryModel.trim() : '';
    const backupModel = backupGateway ? routingDraft.ai.backupModel.trim() : '';

    if (!primaryGateway || !primaryModel) {
      setAiRoutingError(t('settings.aiRouteValidationPrimaryRequired'));
      return;
    }
    if ((backupGateway && !backupModel) || (!backupGateway && backupModel)) {
      setAiRoutingError(t('settings.aiRouteValidationBackupIncomplete'));
      return;
    }

    // Keep channel-editor-owned legacy route list stable to avoid introducing
    // incomplete channel definitions from gateway-only selection.
    const channelRoute = effectiveRoute(splitCsv(allItemMap.get('LLM_CHANNELS')));
    const fallbackRoute = backupModel
      ? effectiveRoute([
        backupModel,
        ...splitCsv(allItemMap.get('LITELLM_FALLBACK_MODELS')).filter((model) => model !== backupModel),
      ])
      : [];
    const confirmation = t('settings.aiRouteSavedDetail', {
      primary: formatRouteLine(primaryGateway, primaryModel),
      backup: formatRouteLine(backupGateway, backupModel),
      scope: t(`settings.aiRouteScope.${aiRoutingScope}`),
    });
    try {
      await saveExternalItems([
        { key: aiRoutingKeys.primaryGateway, value: primaryGateway },
        { key: aiRoutingKeys.primaryModel, value: primaryModel },
        { key: aiRoutingKeys.backupGateway, value: backupGateway },
        { key: aiRoutingKeys.backupModel, value: backupModel },
        { key: 'LLM_CHANNELS', value: channelRoute.join(',') },
        { key: 'LITELLM_MODEL', value: primaryModel },
        { key: 'LITELLM_FALLBACK_MODELS', value: fallbackRoute.join(',') },
      ], confirmation);
      setAiRoutingError(null);
    } catch (error: unknown) {
      if (error instanceof SystemConfigValidationError && error.issues.length > 0) {
        setAiRoutingError(error.issues[0]?.message || t('settings.aiRouteSaveFailed'));
        return;
      }
      const parsed = getParsedApiError(error);
      setAiRoutingError(parsed.message || t('settings.aiRouteSaveFailed'));
    }
  }, [adminLocked, aiRoutingScope, aiRoutingKeys.backupGateway, aiRoutingKeys.backupModel, aiRoutingKeys.primaryGateway, aiRoutingKeys.primaryModel, allItemMap, effectiveRoute, formatRouteLine, routingDraft.ai.backupChannel, routingDraft.ai.backupModel, routingDraft.ai.primaryChannel, routingDraft.ai.primaryModel, saveExternalItems, t]);

  const saveDataRouting = useCallback(async (
    key: string,
    values: Array<string | undefined | null>,
  ) => {
    if (adminLocked) {
      setAdminUnlockError(t('settings.adminSaveLocked'));
      return;
    }
    await saveExternalItems([{ key, value: effectiveRoute(values).join(',') }], t('settings.routeSaved'));
  }, [adminLocked, effectiveRoute, saveExternalItems, t]);

  const saveNotificationRouting = useCallback(async () => {
    if (adminLocked) {
      setAdminUnlockError(t('settings.adminSaveLocked'));
      return;
    }
    await saveExternalItems([
      { key: dataPriorityKeys.notification, value: effectiveRoute([routingDraft.notification.primary, routingDraft.notification.backup]).join(',') },
    ], t('settings.routeSaved'));
  }, [adminLocked, dataPriorityKeys.notification, effectiveRoute, routingDraft.notification.backup, routingDraft.notification.primary, saveExternalItems, t]);
  const saveRuntimeSummaryVisibility = useCallback(async () => {
    if (adminLocked) {
      setAdminUnlockError(t('settings.adminSaveLocked'));
      return;
    }
    await saveExternalItems([
      { key: runtimeSummaryVisibilityKey, value: showRuntimeExecutionSummary ? 'true' : 'false' },
    ], t('settings.routeSaved'));
  }, [adminLocked, runtimeSummaryVisibilityKey, saveExternalItems, showRuntimeExecutionSummary, t]);

  const primarySummaryModel = routingDraft.ai.primaryChannel ? routingDraft.ai.primaryModel : '';
  const backupSummaryModel = routingDraft.ai.backupChannel ? routingDraft.ai.backupModel : '';
  const primaryPresetOptions = primaryGatewayModels.slice(0, 12);
  const backupPresetOptions = backupGatewayModels
    .filter((model) => model !== routingDraft.ai.primaryModel)
    .slice(0, 12);
  const canUsePrimaryCustomModel = Boolean(routingDraft.ai.primaryChannel) && supportsCustomModelId(routingDraft.ai.primaryChannel);
  const canUseBackupCustomModel = Boolean(routingDraft.ai.backupChannel) && supportsCustomModelId(routingDraft.ai.backupChannel);

  return (
    <div className="workspace-page workspace-page--settings">
      <WorkspacePageHeader
        className="shadow-soft-card-strong"
        eyebrow={t('settings.eyebrow')}
        title={t('settings.title')}
        description={t('settings.subtitle')}
        actions={(
          <>
            <p className="workspace-header-actions-note">
              {adminLocked ? t('settings.adminSaveLocked') : t('settings.adminSaveReady')}
            </p>
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
          </>
        )}
      />

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
        <div className="mt-3 flex justify-end">
          <button
            type="button"
            onClick={() => window.location.assign('/admin/logs')}
            className="inline-flex items-center rounded-md border border-border/60 bg-muted/30 px-3 py-1.5 text-xs font-medium text-secondary-text transition-colors hover:text-foreground"
          >
            {t('settings.viewAdminLogs')}
          </button>
        </div>
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
        <div className="space-y-4">
          <SettingsSectionCard
            title={t('settings.domainTitle')}
            description={t('settings.domainDesc')}
          >
            <div className="grid gap-3 xl:grid-cols-4">
              {DOMAIN_ORDER.map((domain) => {
                const nav = domainNavItems.find((item) => item.domain === domain);
                if (!nav) {
                  return null;
                }
                const isActive = activeDomain === domain;
                const count = categories.filter((category) => (categoryDomainMap.get(category.category) || 'advanced') === domain).length;
                return (
                  <button
                    key={domain}
                    type="button"
                    className={isActive
                      ? 'rounded-[1rem] border border-[var(--border-strong)] bg-[var(--pill-active-bg)] px-3 py-3 text-left shadow-[var(--glow-soft)]'
                      : 'rounded-[1rem] border settings-border settings-surface px-3 py-3 text-left hover:settings-surface-hover'}
                    onClick={() => {
                      setActiveDomain(domain);
                      const firstCategory = categories.find(
                        (category) => (categoryDomainMap.get(category.category) || 'advanced') === domain,
                      )?.category;
                      if (firstCategory) {
                        setActiveCategory(firstCategory);
                      }
                    }}
                  >
                    <p className="text-sm font-semibold text-foreground">{nav.title}</p>
                    <p className="mt-1 text-xs leading-5 text-secondary-text">{nav.desc}</p>
                    <p className="mt-2 text-[11px] uppercase tracking-[0.1em] text-muted-text">{count}</p>
                  </button>
                );
              })}
            </div>
          </SettingsSectionCard>

          {activeDomain === 'ai_models' ? (
            <SettingsSectionCard
              title={t('settings.aiEffectiveTitle')}
              description={t('settings.aiEffectiveDesc')}
            >
              <div className="space-y-3">
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
                  <div className="settings-surface rounded-xl border settings-border px-3.5 py-3">
                    <p className="text-xs text-muted-text">{t('settings.aiPrimaryRoute')}</p>
                    <p className="mt-1 break-words text-sm font-semibold text-foreground">
                      {routingDraft.ai.primaryChannel ? prettySourceLabel(routingDraft.ai.primaryChannel) : t('settings.notConfigured')}
                    </p>
                  </div>
                  <div className="settings-surface rounded-xl border settings-border px-3.5 py-3">
                    <p className="text-xs text-muted-text">{t('settings.aiPrimaryModel')}</p>
                    <p className="mt-1 break-words text-sm font-semibold text-foreground">
                      {primarySummaryModel || t('settings.notConfigured')}
                    </p>
                  </div>
                  <div className="settings-surface rounded-xl border settings-border px-3.5 py-3">
                    <p className="text-xs text-muted-text">{t('settings.aiBackupRoute')}</p>
                    <p className="mt-1 break-words text-sm font-semibold text-foreground">
                      {routingDraft.ai.backupChannel ? prettySourceLabel(routingDraft.ai.backupChannel) : t('settings.notConfigured')}
                    </p>
                  </div>
                  <div className="settings-surface rounded-xl border settings-border px-3.5 py-3">
                    <p className="text-xs text-muted-text">{t('settings.aiBackupModel')}</p>
                    <p className="mt-1 break-words text-sm font-semibold text-foreground">
                      {backupSummaryModel || t('settings.notConfigured')}
                    </p>
                  </div>
                  <div className="settings-surface rounded-xl border settings-border px-3.5 py-3">
                    <p className="text-xs text-muted-text">{t('settings.aiRouteStatusLabel')}</p>
                    <p className="mt-1 break-words text-sm font-semibold text-foreground">
                      {t(`settings.aiRouteStatus.${aiSummary.routeStatus}`)}
                    </p>
                    <p className="mt-2 text-xs text-secondary-text">
                      {t('settings.aiConfiguredProviders')}: {aiSummary.configuredProviders.length
                        ? aiSummary.configuredProviders.map(([name, count]) => `${titleCase(name)} (${count})`).join(' · ')
                        : t('settings.notConfigured')}
                    </p>
                  </div>
                </div>

                <div className="settings-surface rounded-xl border settings-border px-4 py-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-foreground">{t('settings.aiDefaultRouteTitle')}</p>
                      <p className="mt-1 text-xs text-muted-text">{t('settings.aiDefaultRouteDesc')}</p>
                      <p className="mt-1 text-xs text-secondary-text">
                        {t('settings.aiRouteScopeLabel')}: {t(`settings.aiRouteScope.${aiRoutingScope}`)}
                      </p>
                      <p className="mt-1 text-[11px] text-muted-text">{t('settings.aiRouteScopeDesc')}</p>
                    </div>
                    {aiSummary.routeMissingButApiConfigured ? (
                      <span className="rounded-full border border-[hsl(var(--accent-warning-hsl)/0.48)] bg-[hsl(var(--accent-warning-hsl)/0.18)] px-2.5 py-1 text-[11px] font-semibold text-[hsl(var(--accent-warning-hsl))]">
                        {t('settings.aiConfiguredNoRoute')}
                      </span>
                    ) : null}
                  </div>
                  {aiSelectorReadinessMismatch ? (
                    <p className="mt-2 rounded-lg border border-[hsl(var(--accent-warning-hsl)/0.4)] bg-[hsl(var(--accent-warning-hsl)/0.12)] px-3 py-2 text-xs text-[hsl(var(--accent-warning-hsl))]">
                      {t('settings.aiGatewaySelectorMismatchWarning')}
                    </p>
                  ) : null}
                  <div className="mt-3 grid gap-3 xl:grid-cols-2">
                    <div className="rounded-xl border border-border/50 bg-base/40 px-3.5 py-3">
                      <p className="text-xs text-muted-text">{t('settings.aiPrimaryRoute')}</p>
                      <Select
                        value={routingDraft.ai.primaryChannel}
                        onChange={(value) => {
                          if (!value) {
                            setAiModelMode((prev) => ({ ...prev, primary: 'preset' }));
                          }
                          if (value && routingDraft.ai.backupChannel === value) {
                            setAiModelMode((prev) => ({ ...prev, backup: 'preset' }));
                          }
                          setRoutingDraft((prev) => ({
                            ...prev,
                            ai: {
                              ...prev.ai,
                              primaryChannel: value,
                              primaryModel: value ? prev.ai.primaryModel : '',
                              backupChannel: prev.ai.backupChannel === value ? '' : prev.ai.backupChannel,
                              backupModel: prev.ai.backupChannel === value ? '' : prev.ai.backupModel,
                            },
                          }));
                        }}
                        options={aiGatewaySelectorOptions.map((channel) => ({ value: channel, label: prettySourceLabel(channel) }))}
                        placeholder={aiGatewaySelectorOptions.length ? t('settings.selectPlaceholder') : t('settings.notConfigured')}
                        disabled={!canSelectPrimaryGateway || adminLocked || isSaving}
                      />
                      {primaryGatewayDisabledReason ? (
                        <p className="mt-2 text-[11px] text-muted-text">{primaryGatewayDisabledReason}</p>
                      ) : null}
                      <p className="mt-2 text-xs text-muted-text">{t('settings.aiModelModeLabel')}</p>
                      <div className="mt-2 flex gap-2">
                        <button
                          type="button"
                          className={aiModelMode.primary === 'preset'
                            ? 'rounded-md border border-[var(--border-strong)] bg-[var(--pill-active-bg)] px-2.5 py-1.5 text-xs font-medium text-foreground'
                            : 'rounded-md border border-border/60 bg-base/60 px-2.5 py-1.5 text-xs text-secondary-text'}
                          onClick={() => setAiModelMode((prev) => ({ ...prev, primary: 'preset' }))}
                          disabled={adminLocked || isSaving || !routingDraft.ai.primaryChannel}
                        >
                          {t('settings.aiModelModePreset')}
                        </button>
                        <button
                          type="button"
                          className={aiModelMode.primary === 'custom'
                            ? 'rounded-md border border-[var(--border-strong)] bg-[var(--pill-active-bg)] px-2.5 py-1.5 text-xs font-medium text-foreground'
                            : 'rounded-md border border-border/60 bg-base/60 px-2.5 py-1.5 text-xs text-secondary-text'}
                          onClick={() => setAiModelMode((prev) => ({ ...prev, primary: 'custom' }))}
                          disabled={adminLocked || isSaving || !routingDraft.ai.primaryChannel || !canUsePrimaryCustomModel}
                        >
                          {t('settings.aiModelModeCustom')}
                        </button>
                      </div>
                      <p className="mt-2 text-[11px] text-muted-text">
                        {!routingDraft.ai.primaryChannel
                          ? t('settings.aiModelModeRequiresGateway')
                          : aiModelMode.primary === 'preset'
                            ? t('settings.aiModelModePresetHint')
                            : t('settings.aiModelModeCustomHint', { gateway: prettySourceLabel(routingDraft.ai.primaryChannel) || t('settings.notConfigured') })}
                      </p>
                      {aiModelMode.primary === 'preset' ? (
                        <Select
                          value={primaryPresetOptions.includes(routingDraft.ai.primaryModel) ? routingDraft.ai.primaryModel : ''}
                          onChange={(value) => setRoutingDraft((prev) => ({
                            ...prev,
                            ai: {
                              ...prev.ai,
                              primaryModel: value,
                              backupModel: prev.ai.backupModel === value ? '' : prev.ai.backupModel,
                            },
                          }))}
                          options={primaryPresetOptions.map((model) => ({ value: model, label: model }))}
                          placeholder={primaryPresetOptions.length ? t('settings.aiPresetModels') : t('settings.notConfigured')}
                          disabled={adminLocked || isSaving || !routingDraft.ai.primaryChannel}
                        />
                      ) : (
                        <Input
                          type="text"
                          label={t('settings.aiCustomModelId')}
                          placeholder={t('settings.aiCustomModelPlaceholder')}
                          value={routingDraft.ai.primaryModel}
                          onChange={(event) => {
                            const value = event.target.value;
                            setRoutingDraft((prev) => ({
                              ...prev,
                              ai: {
                                ...prev.ai,
                                primaryModel: value,
                                backupModel: prev.ai.backupModel === value ? '' : prev.ai.backupModel,
                              },
                            }));
                          }}
                          disabled={adminLocked || isSaving || !canUsePrimaryCustomModel}
                          hint={routingDraft.ai.primaryChannel ? t('settings.aiCustomModelHint') : t('settings.aiModelModeRequiresGateway')}
                        />
                      )}
                      {!primaryModelCompatible && routingDraft.ai.primaryModel ? (
                        <p className="mt-2 text-xs text-[hsl(var(--accent-warning-hsl))]">{t('settings.aiModelCompatibilityWarning')}</p>
                      ) : null}
                    </div>
                    <div className="rounded-xl border border-border/50 bg-base/40 px-3.5 py-3">
                      <p className="text-xs text-muted-text">{t('settings.aiBackupRoute')}</p>
                      <Select
                        value={routingDraft.ai.backupChannel}
                        onChange={(value) => {
                          if (!value) {
                            setAiModelMode((prev) => ({ ...prev, backup: 'preset' }));
                          }
                          setRoutingDraft((prev) => ({
                            ...prev,
                            ai: {
                              ...prev.ai,
                              backupChannel: value,
                              backupModel: value ? prev.ai.backupModel : '',
                            },
                          }));
                        }}
                        options={aiGatewaySelectorOptions
                          .filter((channel) => channel !== routingDraft.ai.primaryChannel)
                          .map((channel) => ({ value: channel, label: prettySourceLabel(channel) }))}
                        placeholder={aiGatewaySelectorOptions.length ? t('settings.selectPlaceholder') : t('settings.notConfigured')}
                        disabled={!canSelectBackupGateway || adminLocked || isSaving}
                      />
                      {backupGatewayDisabledReason ? (
                        <p className="mt-2 text-[11px] text-muted-text">{backupGatewayDisabledReason}</p>
                      ) : null}
                      <p className="mt-2 text-xs text-muted-text">{t('settings.aiModelModeLabel')}</p>
                      <div className="mt-2 flex gap-2">
                        <button
                          type="button"
                          className={aiModelMode.backup === 'preset'
                            ? 'rounded-md border border-[var(--border-strong)] bg-[var(--pill-active-bg)] px-2.5 py-1.5 text-xs font-medium text-foreground'
                            : 'rounded-md border border-border/60 bg-base/60 px-2.5 py-1.5 text-xs text-secondary-text'}
                          onClick={() => setAiModelMode((prev) => ({ ...prev, backup: 'preset' }))}
                          disabled={adminLocked || isSaving || !routingDraft.ai.backupChannel}
                        >
                          {t('settings.aiModelModePreset')}
                        </button>
                        <button
                          type="button"
                          className={aiModelMode.backup === 'custom'
                            ? 'rounded-md border border-[var(--border-strong)] bg-[var(--pill-active-bg)] px-2.5 py-1.5 text-xs font-medium text-foreground'
                            : 'rounded-md border border-border/60 bg-base/60 px-2.5 py-1.5 text-xs text-secondary-text'}
                          onClick={() => setAiModelMode((prev) => ({ ...prev, backup: 'custom' }))}
                          disabled={adminLocked || isSaving || !routingDraft.ai.backupChannel || !canUseBackupCustomModel}
                        >
                          {t('settings.aiModelModeCustom')}
                        </button>
                      </div>
                      <p className="mt-2 text-[11px] text-muted-text">
                        {!routingDraft.ai.backupChannel
                          ? t('settings.aiModelModeRequiresGateway')
                          : aiModelMode.backup === 'preset'
                            ? t('settings.aiModelModePresetHint')
                            : t('settings.aiModelModeCustomHint', { gateway: prettySourceLabel(routingDraft.ai.backupChannel) || t('settings.notConfigured') })}
                      </p>
                      {aiModelMode.backup === 'preset' ? (
                        <Select
                          value={backupPresetOptions.includes(routingDraft.ai.backupModel) ? routingDraft.ai.backupModel : ''}
                          onChange={(value) => setRoutingDraft((prev) => ({
                            ...prev,
                            ai: {
                              ...prev.ai,
                              backupModel: value,
                            },
                          }))}
                          options={backupPresetOptions.map((model) => ({ value: model, label: model }))}
                          placeholder={backupPresetOptions.length ? t('settings.aiPresetModels') : t('settings.notConfigured')}
                          disabled={adminLocked || isSaving || !routingDraft.ai.backupChannel}
                        />
                      ) : (
                        <Input
                          type="text"
                          label={t('settings.aiCustomModelId')}
                          placeholder={t('settings.aiCustomModelPlaceholder')}
                          value={routingDraft.ai.backupModel}
                          onChange={(event) => setRoutingDraft((prev) => ({
                            ...prev,
                            ai: {
                              ...prev.ai,
                              backupModel: event.target.value,
                            },
                          }))}
                          disabled={adminLocked || isSaving || !canUseBackupCustomModel}
                          hint={routingDraft.ai.backupChannel ? t('settings.aiCustomModelHint') : t('settings.aiModelModeRequiresGateway')}
                        />
                      )}
                      {!backupModelCompatible && routingDraft.ai.backupModel ? (
                        <p className="mt-2 text-xs text-[hsl(var(--accent-warning-hsl))]">{t('settings.aiModelCompatibilityWarning')}</p>
                      ) : null}
                    </div>
                  </div>
                  <div className="mt-3 flex justify-end">
                    <Button
                      type="button"
                      size="sm"
                      variant="settings-primary"
                      onClick={() => void saveAiRouting()}
                      disabled={adminLocked || isSaving}
                    >
                      {t('settings.saveRoute')}
                    </Button>
                  </div>
                  {aiRoutingError ? (
                    <p className="mt-2 rounded-lg border border-[hsl(var(--accent-warning-hsl)/0.4)] bg-[hsl(var(--accent-warning-hsl)/0.12)] px-3 py-2 text-xs text-[hsl(var(--accent-warning-hsl))]">
                      {aiRoutingError}
                    </p>
                  ) : null}
                </div>

                <div className="settings-surface rounded-xl border settings-border px-4 py-4">
                  <p className="text-sm font-semibold text-foreground">{t('settings.aiProviderReadinessTitle')}</p>
                  <p className="mt-1 text-xs text-muted-text">{t('settings.aiProviderReadinessDesc')}</p>
                  <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                    {aiGatewayReadiness.map((provider) => (
                      <div key={provider.gateway} className="rounded-xl border border-border/50 bg-base/40 px-3 py-2.5">
                        <p className="text-sm font-semibold text-foreground">{provider.label}</p>
                        <p className="mt-1 text-xs text-secondary-text">
                          {provider.credentialReady ? t('settings.aiProviderReady') : t('settings.aiProviderMissingCredential')}
                          {provider.credentialReady ? ` · ${provider.credentialCount}` : ''}
                        </p>
                        <p className="mt-1 text-xs text-muted-text">
                          {t('settings.aiPresetModels')}: {provider.presetCount}
                          {' · '}
                          {t('settings.aiInferredModels')}: {provider.inferredCount}
                        </p>
                        <p className="mt-1 text-xs text-muted-text">
                          {t('settings.aiCustomModelId')}: {provider.supportsCustom ? t('settings.enabledState') : t('settings.disabledState')}
                        </p>
                        <p className="mt-1 text-xs text-muted-text">
                          {provider.noteKey === 'aihubmix_dynamic_pool'
                            ? t('settings.aiProviderNoteAihubmix')
                            : provider.noteKey === 'gemini_multi_model_single_key'
                              ? t('settings.aiProviderNoteGemini')
                              : provider.noteKey === 'openai_compatible_dynamic'
                                ? t('settings.aiProviderNoteOpenAICompatible')
                                : t('settings.aiProviderNoteGeneric')}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="rounded-xl border border-border/50 bg-muted/10 px-4 py-3">
                  <p className="text-sm font-semibold text-foreground">{t('settings.aiAdvancedTitle')}</p>
                  <p className="mt-1 text-xs text-muted-text">{t('settings.aiAdvancedDesc')}</p>
                  <button
                    type="button"
                    className="mt-2 inline-flex items-center rounded-md border border-border/60 bg-base/60 px-3 py-1.5 text-xs text-secondary-text hover:text-foreground"
                    onClick={() => setActiveCategory('ai_model')}
                  >
                    {t('settings.aiAdvancedJump')}
                  </button>
                </div>
              </div>
            </SettingsSectionCard>
          ) : null}

          {activeDomain === 'data_sources' ? (
            <SettingsSectionCard
              title={t('settings.dataEffectiveTitle')}
              description={t('settings.dataEffectiveDesc')}
            >
              <div className="grid gap-3 xl:grid-cols-2">
                {[
                  {
                    key: 'market' as const,
                    role: t('settings.marketDataRole'),
                    values: effectiveRoute([routingDraft.market.primary, routingDraft.market.backup, routingDraft.market.fallback]),
                    available: availableProviders.market,
                    onSave: () => saveDataRouting(dataPriorityKeys.market, [
                      routingDraft.market.primary,
                      routingDraft.market.backup,
                      routingDraft.market.fallback,
                    ]),
                  },
                  {
                    key: 'fundamentals' as const,
                    role: t('settings.fundamentalDataRole'),
                    values: effectiveRoute([routingDraft.fundamentals.primary, routingDraft.fundamentals.backup, routingDraft.fundamentals.fallback]),
                    available: availableProviders.fundamentals,
                    onSave: () => saveDataRouting(dataPriorityKeys.fundamentals, [
                      routingDraft.fundamentals.primary,
                      routingDraft.fundamentals.backup,
                      routingDraft.fundamentals.fallback,
                    ]),
                  },
                  {
                    key: 'news' as const,
                    role: t('settings.newsDataRole'),
                    values: effectiveRoute([routingDraft.news.primary, routingDraft.news.backup]),
                    available: availableProviders.news,
                    onSave: () => saveDataRouting(dataPriorityKeys.news, [
                      routingDraft.news.primary,
                      routingDraft.news.backup,
                    ]),
                  },
                  {
                    key: 'sentiment' as const,
                    role: t('settings.sentimentDataRole'),
                    values: effectiveRoute([routingDraft.sentiment.primary, routingDraft.sentiment.backup]),
                    available: availableProviders.sentiment,
                    onSave: () => saveDataRouting(dataPriorityKeys.sentiment, [
                      routingDraft.sentiment.primary,
                      routingDraft.sentiment.backup,
                    ]),
                  },
                ].map((group) => (
                  <div key={group.role} className="settings-surface rounded-xl border settings-border px-3.5 py-3">
                    <p className="text-xs text-muted-text">{group.role}</p>
                    {group.values.length ? (
                      <>
                        <p className="mt-2 text-xs text-secondary-text">{group.values.map((source) => prettySourceLabel(source)).join(' -> ')}</p>
                        <ul className="mt-2 space-y-1.5 text-sm">
                        {group.values.map((source, index) => (
                          <li key={`${group.role}-${source}-${index}`} className="flex items-center justify-between gap-3">
                            <span className={sourceToneClass(index)}>{priorityLabel(index)}</span>
                            <span className="truncate text-secondary-text">{prettySourceLabel(source)}</span>
                          </li>
                        ))}
                        </ul>
                      </>
                    ) : (
                      <p className="mt-2 text-sm text-muted-text">
                        {group.available.length ? t('settings.configuredNoPriority') : t('settings.notConfigured')}
                      </p>
                    )}
                    <div className="mt-3 grid gap-2 sm:grid-cols-3">
                      <Select
                        value={group.key === 'market' ? routingDraft.market.primary : group.key === 'fundamentals' ? routingDraft.fundamentals.primary : group.key === 'news' ? routingDraft.news.primary : routingDraft.sentiment.primary}
                        onChange={(value) => setRouteTier(group.key, 'primary', value)}
                        options={group.available.map((provider) => ({ value: provider, label: prettySourceLabel(provider) }))}
                        placeholder={group.available.length ? t('settings.selectPlaceholder') : t('settings.notConfigured')}
                        disabled={adminLocked || isSaving || group.available.length === 0}
                      />
                      <Select
                        value={group.key === 'market' ? routingDraft.market.backup : group.key === 'fundamentals' ? routingDraft.fundamentals.backup : group.key === 'news' ? routingDraft.news.backup : routingDraft.sentiment.backup}
                        onChange={(value) => setRouteTier(group.key, 'backup', value)}
                        options={group.available
                          .filter((provider) => {
                            const primary = group.key === 'market'
                              ? routingDraft.market.primary
                              : group.key === 'fundamentals'
                                ? routingDraft.fundamentals.primary
                                : group.key === 'news'
                                  ? routingDraft.news.primary
                                  : routingDraft.sentiment.primary;
                            return provider !== primary;
                          })
                          .map((provider) => ({ value: provider, label: prettySourceLabel(provider) }))}
                        placeholder={group.available.length ? t('settings.selectPlaceholder') : t('settings.notConfigured')}
                        disabled={adminLocked || isSaving || group.available.length < 2}
                      />
                      {group.key === 'market' || group.key === 'fundamentals' ? (
                        <Select
                          value={group.key === 'market' ? routingDraft.market.fallback : routingDraft.fundamentals.fallback}
                          onChange={(value) => setRouteTier(group.key, 'fallback', value)}
                          options={group.available
                            .filter((provider) => {
                              const primary = group.key === 'market' ? routingDraft.market.primary : routingDraft.fundamentals.primary;
                              const backup = group.key === 'market' ? routingDraft.market.backup : routingDraft.fundamentals.backup;
                              return provider !== primary && provider !== backup;
                            })
                            .map((provider) => ({ value: provider, label: prettySourceLabel(provider) }))}
                          placeholder={group.available.length ? t('settings.selectPlaceholder') : t('settings.notConfigured')}
                          disabled={adminLocked || isSaving || group.available.length < 3}
                        />
                      ) : <div />}
                    </div>
                    <div className="mt-2 flex justify-end">
                      <Button
                        type="button"
                        size="sm"
                        variant="settings-secondary"
                        disabled={adminLocked || isSaving}
                        onClick={() => void group.onSave()}
                      >
                        {t('settings.saveRoute')}
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </SettingsSectionCard>
          ) : null}

          {activeDomain === 'notifications' ? (
            <SettingsSectionCard
              title={t('settings.notificationEffectiveTitle')}
              description={t('settings.notificationEffectiveDesc')}
            >
              <div className="grid gap-3 md:grid-cols-3">
                <div className="settings-surface rounded-xl border settings-border px-3.5 py-3">
                  <p className="text-xs text-muted-text">{t('settings.notificationEnabledChannels')}</p>
                  <p className="mt-1 break-words text-sm font-semibold text-foreground">
                    {notificationSummary.enabledChannels.length
                      ? notificationSummary.enabledChannels.map((key) => prettySourceLabel(key)).join(' · ')
                      : (notificationSummary.configuredChannels.length ? t('settings.configuredNoPriority') : t('settings.notConfigured'))}
                  </p>
                </div>
                <div className="settings-surface rounded-xl border settings-border px-3.5 py-3">
                  <p className="text-xs text-muted-text">{t('settings.notificationPrimaryChannel')}</p>
                  <p className="mt-1 break-words text-sm font-semibold text-foreground">
                    {routingDraft.notification.primary ? prettySourceLabel(routingDraft.notification.primary) : t('settings.notConfigured')}
                  </p>
                  <p className="mt-2 text-xs text-secondary-text">
                    {t('settings.notificationBackupChannels')}: {routingDraft.notification.backup
                      ? prettySourceLabel(routingDraft.notification.backup)
                      : t('settings.notConfigured')}
                  </p>
                </div>
                <div className="settings-surface rounded-xl border settings-border px-3.5 py-3">
                  <p className="text-xs text-muted-text">{t('settings.notificationDestinations')}</p>
                  <p className="mt-1 break-words text-sm font-semibold text-foreground">
                    {notificationSummary.destinations.length
                      ? notificationSummary.destinations.map((key) => titleCase(key)).join(' · ')
                      : t('settings.notConfigured')}
                  </p>
                </div>
              </div>
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <div className="settings-surface rounded-xl border settings-border px-3.5 py-3">
                  <p className="text-xs text-muted-text">{t('settings.notificationPrimaryChannel')}</p>
                  <Select
                    value={routingDraft.notification.primary}
                    onChange={(value) => setRouteTier('notification', 'primary', value)}
                    options={notificationSummary.configuredChannels.map((channel) => ({
                      value: channel,
                      label: prettySourceLabel(channel),
                    }))}
                    placeholder={notificationSummary.configuredChannels.length ? t('settings.selectPlaceholder') : t('settings.notConfigured')}
                    disabled={adminLocked || isSaving || notificationSummary.configuredChannels.length === 0}
                  />
                </div>
                <div className="settings-surface rounded-xl border settings-border px-3.5 py-3">
                  <p className="text-xs text-muted-text">{t('settings.notificationBackupChannels')}</p>
                  <Select
                    value={routingDraft.notification.backup}
                    onChange={(value) => setRouteTier('notification', 'backup', value)}
                    options={notificationSummary.configuredChannels
                      .filter((channel) => channel !== routingDraft.notification.primary)
                      .map((channel) => ({
                        value: channel,
                        label: prettySourceLabel(channel),
                      }))}
                    placeholder={notificationSummary.configuredChannels.length ? t('settings.selectPlaceholder') : t('settings.notConfigured')}
                    disabled={adminLocked || isSaving || notificationSummary.configuredChannels.length < 2}
                  />
                </div>
              </div>
              <div className="mt-3 flex justify-end">
                <Button
                  type="button"
                  size="sm"
                  variant="settings-primary"
                  disabled={adminLocked || isSaving}
                  onClick={() => void saveNotificationRouting()}
                >
                  {t('settings.saveRoute')}
                </Button>
              </div>
            </SettingsSectionCard>
          ) : null}
          {activeDomain === 'advanced' ? (
            <SettingsSectionCard
              title={t('settings.runtimeSummaryVisibilityTitle')}
              description={t('settings.runtimeSummaryVisibilityDesc')}
            >
              <div className="settings-surface rounded-xl border settings-border px-3.5 py-3">
                <p className="text-xs text-muted-text">{t('settings.runtimeSummaryVisibilityTitle')}</p>
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setShowRuntimeExecutionSummary(true)}
                    className={showRuntimeExecutionSummary
                      ? 'rounded-lg border border-[var(--border-strong)] bg-[var(--pill-active-bg)] px-3 py-2 text-sm text-foreground shadow-[var(--glow-soft)]'
                      : 'rounded-lg border border-[var(--border-muted)] bg-[var(--pill-bg)] px-3 py-2 text-sm text-secondary-text hover:border-[var(--border-strong)] hover:text-foreground'}
                    disabled={adminLocked || isSaving}
                  >
                    {t('settings.runtimeSummaryVisibleOn')}
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowRuntimeExecutionSummary(false)}
                    className={!showRuntimeExecutionSummary
                      ? 'rounded-lg border border-[var(--border-strong)] bg-[var(--pill-active-bg)] px-3 py-2 text-sm text-foreground shadow-[var(--glow-soft)]'
                      : 'rounded-lg border border-[var(--border-muted)] bg-[var(--pill-bg)] px-3 py-2 text-sm text-secondary-text hover:border-[var(--border-strong)] hover:text-foreground'}
                    disabled={adminLocked || isSaving}
                  >
                    {t('settings.runtimeSummaryVisibleOff')}
                  </button>
                </div>
                <div className="mt-3 flex justify-end">
                  <Button
                    type="button"
                    size="sm"
                    variant="settings-primary"
                    onClick={() => void saveRuntimeSummaryVisibility()}
                    disabled={adminLocked || isSaving}
                  >
                    {t('settings.runtimeSummaryVisibilitySave')}
                  </Button>
                </div>
              </div>
            </SettingsSectionCard>
          ) : null}

          <div className="workspace-split-layout">
          <aside className="workspace-split-rail">
            <SettingsCategoryNav
              categories={domainCategories}
              itemsByCategory={itemsByCategory}
              activeCategory={activeCategory}
              onSelect={setActiveCategory}
              disabled={adminLocked}
            />
          </aside>

          <section className="workspace-split-main space-y-4">
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
                  onMergeStockList={async (value) => {
                    if (adminLocked) {
                      return;
                    }
                    await saveExternalItems([{ key: 'STOCK_LIST', value }], '自选股配置已更新');
                  }}
                  disabled={isSaving || isLoading || adminLocked}
                />
              </SettingsSectionCard>
            ) : null}
            {activeCategory === 'ai_model' ? (
              <SettingsSectionCard
                title={t('settings.aiAdvancedTitle')}
                description={t('settings.aiAdvancedDesc')}
              >
                <details className="group rounded-xl border border-border/50 bg-base/40 px-3 py-3">
                  <summary className="cursor-pointer list-none text-sm font-medium text-foreground">
                    {t('settings.aiAdvancedToggle')}
                  </summary>
                  <div className="mt-3">
                    <LLMChannelEditor
                      items={rawActiveItems}
                      adminUnlockToken={adminUnlockToken}
                      onSaveItems={async (updatedItems, successMessage) => {
                        if (adminLocked) {
                          return;
                        }
                        await saveExternalItems(updatedItems, successMessage);
                      }}
                      disabled={isSaving || isLoading || adminLocked}
                    />
                  </div>
                </details>
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
                {activeCategory === 'ai_model' ? (
                  <details className="group rounded-xl border border-border/50 bg-base/40 px-3 py-3">
                    <summary className="cursor-pointer list-none text-sm font-medium text-foreground">
                      {t('settings.aiRawFieldsToggle')}
                    </summary>
                    <div className="mt-3 space-y-3">
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
                    </div>
                  </details>
                ) : (
                  activeItems.map((item) => (
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
                  ))
                )}
              </SettingsSectionCard>
            ) : (
              <div className="settings-panel-muted rounded-[1.5rem] border p-5 shadow-soft-card">
                <p className="settings-accent-text text-xs font-semibold uppercase tracking-[0.22em]">
                  {t('settings.currentCategory')}
                </p>
                <p className="mt-2 text-sm font-semibold text-foreground">
                  {t('settings.noItems')}
                </p>
                <p className="mt-2 text-xs leading-6 text-muted-text">
                  {getCategoryDescription(language, activeCategory as SystemConfigCategory, '') || t('settings.currentCategoryDesc')}
                </p>
              </div>
            )}
          </section>
          </div>
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
