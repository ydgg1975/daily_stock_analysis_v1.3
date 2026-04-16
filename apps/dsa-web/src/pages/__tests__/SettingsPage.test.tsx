import type React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import SettingsPage from '../SettingsPage';

const {
  load,
  clearToast,
  setActiveCategory,
  save,
  saveExternalItems,
  resetDraft,
  setDraftValue,
  applyPartialUpdate,
  setAdminUnlockSession,
  clearAdminUnlockSession,
  refreshStatus,
  setThemeStyle,
  testLLMChannel,
  resetRuntimeCaches,
  factoryResetSystem,
  useAuthMock,
  useSystemConfigMock,
} = vi.hoisted(() => ({
  load: vi.fn(),
  clearToast: vi.fn(),
  setActiveCategory: vi.fn(),
  save: vi.fn(),
  saveExternalItems: vi.fn(),
  resetDraft: vi.fn(),
  setDraftValue: vi.fn(),
  applyPartialUpdate: vi.fn(),
  setAdminUnlockSession: vi.fn(),
  clearAdminUnlockSession: vi.fn(),
  refreshStatus: vi.fn(),
  setThemeStyle: vi.fn(),
  testLLMChannel: vi.fn(),
  resetRuntimeCaches: vi.fn(),
  factoryResetSystem: vi.fn(),
  useAuthMock: vi.fn(),
  useSystemConfigMock: vi.fn(),
}));

vi.mock('../../api/systemConfig', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/systemConfig')>();
  return {
    ...actual,
    systemConfigApi: {
      ...actual.systemConfigApi,
      testLLMChannel,
      resetRuntimeCaches,
      factoryResetSystem,
    },
  };
});

vi.mock('../../hooks', () => ({
  useAuth: () => useAuthMock(),
  useSystemConfig: () => useSystemConfigMock(),
}));

vi.mock('../../components/theme/ThemeProvider', () => ({
  useThemeStyle: () => ({
    themeStyle: 'terminal',
    setThemeStyle,
  }),
}));

vi.mock('../../components/settings', () => ({
  AuthSettingsCard: () => <div>认证与登录保护</div>,
  ChangePasswordCard: () => <div>修改密码</div>,
  IntelligentImport: ({ onMergeStockList }: { onMergeStockList: (value: string) => void }) => (
    <button type="button" onClick={() => onMergeStockList('SZ000001,SZ000002')}>
      merge stock list
    </button>
  ),
  FontSizeSettingsCard: () => <div>字体大小</div>,
  LLMChannelEditor: ({
    onSaveItems,
    providerScopeName,
    focusChannelName,
    externalCreatePreset,
    onExternalCreateHandled,
  }: {
    onSaveItems: (items: Array<{ key: string; value: string }>, successMessage: string) => void;
    providerScopeName?: string;
    focusChannelName?: string;
    externalCreatePreset?: string | null;
    onExternalCreateHandled?: () => void;
  }) => (
    <div>
      <button
        type="button"
        onClick={() => onSaveItems([{ key: 'LLM_CHANNELS', value: 'primary,backup' }], '渠道配置已保存')}
      >
        save llm channels
      </button>
      <p data-testid="llm-provider-scope">{providerScopeName || ''}</p>
      <p data-testid="llm-focus-channel">{focusChannelName || ''}</p>
      {externalCreatePreset ? (
        <button type="button" onClick={() => onExternalCreateHandled?.()}>
          external create {externalCreatePreset}
        </button>
      ) : null}
    </div>
  ),
  SettingsAlert: ({ title, message }: { title: string; message: string }) => (
    <div>
      {title}:{message}
    </div>
  ),
  SettingsCategoryNav: ({
    categories,
    activeCategory,
    onSelect,
  }: {
    categories: Array<{ category: string; title: string }>;
    activeCategory: string;
    onSelect: (value: string) => void;
  }) => (
    <nav>
      {categories.map((category) => (
        <button
          key={category.category}
          type="button"
          aria-pressed={activeCategory === category.category}
          onClick={() => onSelect(category.category)}
        >
          {category.title}
        </button>
      ))}
    </nav>
  ),
  SettingsField: ({ item }: { item: { key: string } }) => <div>{item.key}</div>,
  SettingsLoading: () => <div>loading</div>,
  SettingsSectionCard: ({
    title,
    description,
    children,
  }: {
    title: string;
    description?: string;
    children: React.ReactNode;
  }) => (
    <section>
      <h2>{title}</h2>
      {description ? <p>{description}</p> : null}
      {children}
    </section>
  ),
}));

const baseCategories = [
  { category: 'system', title: 'System', description: '系统设置', displayOrder: 1, fields: [] },
  { category: 'base', title: 'Base', description: '基础配置', displayOrder: 2, fields: [] },
  { category: 'ai_model', title: 'AI', description: '模型配置', displayOrder: 3, fields: [] },
  { category: 'data_source', title: 'Data', description: '数据源配置', displayOrder: 4, fields: [] },
  { category: 'agent', title: 'Agent', description: 'Agent 配置', displayOrder: 5, fields: [] },
];

type ConfigState = {
  categories: Array<{ category: string; title: string; description: string; displayOrder: number; fields: [] }>;
  itemsByCategory: Record<string, Array<Record<string, unknown>>>;
  issueByKey: Record<string, unknown[]>;
  activeCategory: string;
  setActiveCategory: typeof setActiveCategory;
  hasDirty: boolean;
  dirtyCount: number;
  toast: null;
  clearToast: typeof clearToast;
  isLoading: boolean;
  isSaving: boolean;
  loadError: null;
  saveError: null;
  retryAction: null;
  load: typeof load;
  retry: ReturnType<typeof vi.fn>;
  save: typeof save;
  saveExternalItems: typeof saveExternalItems;
  resetDraft: typeof resetDraft;
  setDraftValue: typeof setDraftValue;
  applyPartialUpdate: typeof applyPartialUpdate;
  adminUnlockToken: string | null;
  adminUnlockExpiresAt: number | null;
  isAdminUnlocked: boolean;
  setAdminUnlockSession: typeof setAdminUnlockSession;
  clearAdminUnlockSession: typeof clearAdminUnlockSession;
};

type ConfigOverride = Partial<ConfigState>;

function buildSystemConfigState(overrides: ConfigOverride = {}) {
  return {
    categories: baseCategories,
    itemsByCategory: {
      system: [
        {
          key: 'ADMIN_AUTH_ENABLED',
          value: 'true',
          rawValueExists: true,
          isMasked: false,
          schema: {
            key: 'ADMIN_AUTH_ENABLED',
            category: 'system',
            dataType: 'boolean',
            uiControl: 'switch',
            isSensitive: false,
            isRequired: false,
            isEditable: true,
            options: [],
            validation: {},
            displayOrder: 1,
          },
        },
      ],
      base: [
        {
          key: 'STOCK_LIST',
          value: 'SH600000',
          rawValueExists: true,
          isMasked: false,
          schema: {
            key: 'STOCK_LIST',
            category: 'base',
            dataType: 'string',
            uiControl: 'textarea',
            isSensitive: false,
            isRequired: false,
            isEditable: true,
            options: [],
            validation: {},
            displayOrder: 1,
          },
        },
      ],
      ai_model: [
        {
          key: 'LLM_CHANNELS',
          value: 'primary',
          rawValueExists: true,
          isMasked: false,
          schema: {
            key: 'LLM_CHANNELS',
            category: 'ai_model',
            dataType: 'string',
            uiControl: 'textarea',
            isSensitive: false,
            isRequired: false,
            isEditable: true,
            options: [],
            validation: {},
            displayOrder: 1,
          },
        },
      ],
      data_source: [
        {
          key: 'REALTIME_SOURCE_PRIORITY',
          value: 'finnhub,yahoo',
          rawValueExists: true,
          isMasked: false,
          schema: {
            key: 'REALTIME_SOURCE_PRIORITY',
            category: 'data_source',
            dataType: 'string',
            uiControl: 'text',
            isSensitive: false,
            isRequired: false,
            isEditable: true,
            options: [],
            validation: {},
            displayOrder: 1,
          },
        },
        {
          key: 'FINNHUB_API_KEY',
          value: 'masked-finnhub-token',
          rawValueExists: true,
          isMasked: false,
          schema: {
            key: 'FINNHUB_API_KEY',
            category: 'data_source',
            dataType: 'string',
            uiControl: 'text',
            isSensitive: true,
            isRequired: false,
            isEditable: true,
            options: [],
            validation: {},
            displayOrder: 2,
          },
        },
      ],
      agent: [
        {
          key: 'AGENT_ORCHESTRATOR_TIMEOUT_S',
          value: '600',
          rawValueExists: true,
          isMasked: false,
          schema: {
            key: 'AGENT_ORCHESTRATOR_TIMEOUT_S',
            category: 'agent',
            dataType: 'integer',
            uiControl: 'number',
            isSensitive: false,
            isRequired: false,
            isEditable: true,
            options: [],
            validation: {},
            displayOrder: 1,
          },
        },
      ],
    },
    issueByKey: {},
    activeCategory: 'system',
    setActiveCategory,
    hasDirty: false,
    dirtyCount: 0,
    toast: null,
    clearToast,
    isLoading: false,
    isSaving: false,
    loadError: null,
    saveError: null,
    retryAction: null,
    load,
    retry: vi.fn(),
    save,
    saveExternalItems,
    resetDraft,
    setDraftValue,
    applyPartialUpdate,
    adminUnlockToken: 'unit-test-token',
    adminUnlockExpiresAt: Date.now() + 60_000,
    isAdminUnlocked: true,
    setAdminUnlockSession,
    clearAdminUnlockSession,
    ...overrides,
  };
}

async function openAiRoutingDrawer() {
  fireEvent.click(screen.getByRole('button', { name: '编辑任务路由' }));
  await waitFor(() => {
    expect(screen.getByRole('dialog', { name: '任务路由编辑' })).toBeInTheDocument();
  });
}

async function openAdvancedConfigDrawer() {
  fireEvent.click(screen.getByRole('button', { name: '打开高级设置' }));
  await waitFor(() => {
    expect(screen.getByRole('dialog', { name: '高级 Provider / Channel 编辑' })).toBeInTheDocument();
  });
  expect(screen.getByTestId('llm-provider-scope')).toHaveTextContent('');
}

function openMaintenancePanel(summaryLabel = '展开维护操作与日志入口') {
  const summary = screen.getByText(summaryLabel);
  const details = summary.closest('details');
  expect(details).not.toBeNull();
  expect(details).not.toHaveAttribute('open');
  fireEvent.click(summary.closest('summary') ?? summary);
  expect(details).toHaveAttribute('open');
}

function getMaintenancePanel(summaryLabel = '展开维护操作与日志入口') {
  const summary = screen.getByText(summaryLabel);
  return summary.closest('details');
}

async function openQuickProviderDrawer(providerName: string) {
  const providerKey = providerName === 'AIHubMix'
    ? 'aihubmix'
    : providerName === 'OpenAI'
      ? 'openai'
      : providerName === 'GLM / Zhipu'
        ? 'zhipu'
        : providerName.toLowerCase();
  const providerSection = screen.getByTestId('ai-provider-quick-section');
  const providerCard = within(providerSection).getByTestId(`ai-provider-card-${providerKey}`);
  fireEvent.click(within(providerCard as HTMLElement).getByRole('button', { name: '打开快速配置' }));
  await waitFor(() => {
    expect(screen.getByRole('dialog', { name: `${providerName} 快速配置` })).toBeInTheDocument();
  });
  return providerCard as HTMLElement;
}

function buildAiConfigItem(key: string, value: string) {
  return {
    key,
    value,
    rawValueExists: value.trim().length > 0,
    isMasked: false,
    schema: {
      key,
      category: 'ai_model',
      dataType: 'string',
      uiControl: 'text',
      isSensitive: /KEY/i.test(key),
      isRequired: false,
      isEditable: true,
      options: [],
      validation: {},
      displayOrder: 1,
    },
  };
}

function buildDataSourceConfigItem(key: string, value: string) {
  return {
    key,
    value,
    rawValueExists: value.trim().length > 0,
    isMasked: /KEY/i.test(key),
    schema: {
      key,
      category: 'data_source',
      dataType: 'string',
      uiControl: 'text',
      isSensitive: /KEY/i.test(key),
      isRequired: false,
      isEditable: true,
      options: [],
      validation: {},
      displayOrder: 1,
    },
  };
}

describe('SettingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.innerWidth = 1280;
    window.dispatchEvent(new Event('resize'));
    window.sessionStorage.clear();
    useAuthMock.mockReturnValue({
      authEnabled: true,
      passwordChangeable: true,
      setupState: 'enabled',
      refreshStatus,
    });
    useSystemConfigMock.mockReturnValue(buildSystemConfigState());
    testLLMChannel.mockResolvedValue({
      success: true,
      message: 'ok',
      resolvedModel: 'gemini/gemini-2.5-flash',
      latencyMs: 123,
    });
    resetRuntimeCaches.mockResolvedValue({
      success: true,
      action: 'reset_runtime_caches',
      message: '运行时 provider/search 缓存已重置。',
      cleared: ['data_fetcher_manager', 'search_service'],
    });
    factoryResetSystem.mockResolvedValue({
      success: true,
      action: 'factory_reset_system',
      message: 'Factory reset completed',
      cleared: ['non_bootstrap_users', 'user_sessions', 'analysis_history'],
      preserved: ['bootstrap_admin_access', 'system_configuration', 'execution_logs'],
      counts: {
        users: 2,
        sessions: 3,
        analysisHistory: 4,
      },
      confirmationPhrase: 'FACTORY RESET',
    });
  });

  it('renders category navigation and auth settings modules', async () => {
    render(<SettingsPage />);

    expect(await screen.findByRole('heading', { name: '系统控制面' })).toBeInTheDocument();
    expect(await screen.findByText('认证与登录保护')).toBeInTheDocument();
    expect(await screen.findByText('修改密码')).toBeInTheDocument();
    expect(load).toHaveBeenCalled();
  });

  it('renders the admin control plane directly without a second unlock wall', async () => {
    window.sessionStorage.clear();
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'system',
      hasDirty: false,
      adminUnlockToken: null,
      adminUnlockExpiresAt: null,
    }));

    render(<SettingsPage />);

    expect(await screen.findByText('全局控制面概览')).toBeInTheDocument();
    expect(screen.getAllByText('当前已进入全局系统控制面').length).toBeGreaterThan(0);
    expect(screen.getByText('展开维护操作与日志入口')).toBeInTheDocument();
    expect(getMaintenancePanel()).not.toHaveAttribute('open');
    expect(screen.getByText('认证与登录保护')).toBeInTheDocument();
    expect(screen.getByText('修改密码')).toBeInTheDocument();
    expect(screen.queryByText('锁定状态下仅可浏览，无法修改系统级配置。')).not.toBeInTheDocument();
  });

  it('keeps the admin control plane focused on global domains without personal notification settings', async () => {
    render(<SettingsPage />);

    expect(await screen.findByText('全局控制面概览')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '通知与告警' })).not.toBeInTheDocument();
    expect(screen.queryByText('个人通知渠道')).not.toBeInTheDocument();
  });

  it('confirms and runs bounded admin maintenance actions at action level', async () => {
    render(<SettingsPage />);

    openMaintenancePanel();
    fireEvent.click(screen.getByRole('button', { name: '重置运行时缓存' }));

    expect(await screen.findByText('确认重置运行时缓存')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '确认执行' }));

    await waitFor(() => {
      expect(resetRuntimeCaches).toHaveBeenCalledTimes(1);
    });
    await waitFor(() => {
      expect(screen.getByText(/成功:运行时 provider\/search 缓存已重置。/)).toBeInTheDocument();
    });
  });

  it('separates safe maintenance from factory reset and requires a typed phrase before destructive execution', async () => {
    render(<SettingsPage />);

    openMaintenancePanel();
    expect(screen.getByText('维护操作')).toBeInTheDocument();
    expect(screen.getByText('工厂重置 / 系统初始化')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '执行工厂重置' }));

    expect(await screen.findByText('确认工厂重置')).toBeInTheDocument();
    const confirmButton = screen.getByRole('button', { name: '确认执行' });
    expect(confirmButton).toBeDisabled();

    fireEvent.change(screen.getByLabelText('输入确认短语'), { target: { value: 'WRONG' } });
    expect(confirmButton).toBeDisabled();

    fireEvent.change(screen.getByLabelText('输入确认短语'), { target: { value: 'FACTORY RESET' } });
    expect(confirmButton).not.toBeDisabled();

    fireEvent.click(confirmButton);

    await waitFor(() => {
      expect(factoryResetSystem).toHaveBeenCalledWith({ confirmationPhrase: 'FACTORY RESET' });
    });
  });

  it('keeps maintenance and destructive actions out of the primary control-plane surface until expanded', async () => {
    render(<SettingsPage />);

    expect(await screen.findByText('全局控制面概览')).toBeInTheDocument();
    expect(screen.getByText('展开维护操作与日志入口')).toBeInTheDocument();
    expect(getMaintenancePanel()).not.toHaveAttribute('open');

    openMaintenancePanel();

    expect(getMaintenancePanel()).toHaveAttribute('open');
    expect(screen.getByRole('button', { name: '查看系统执行日志' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '重置运行时缓存' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '执行工厂重置' })).toBeInTheDocument();
  });

  it('resets local drafts from the page header button', () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({ hasDirty: true, dirtyCount: 2 }));

    render(<SettingsPage />);

    // Clear the initial load call from useEffect
    vi.clearAllMocks();

    fireEvent.click(screen.getByRole('button', { name: '重置' }));

    // Reset should call resetDraft and NOT call load
    expect(resetDraft).toHaveBeenCalledTimes(1);
    expect(load).not.toHaveBeenCalled();
  });

  it('hides unavailable deep research and event monitor fields from the agent category', () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'agent',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        agent: [
          {
            key: 'AGENT_ORCHESTRATOR_TIMEOUT_S',
            value: '600',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'AGENT_ORCHESTRATOR_TIMEOUT_S',
              category: 'agent',
              dataType: 'integer',
              uiControl: 'number',
              isSensitive: false,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 1,
            },
          },
          {
            key: 'AGENT_DEEP_RESEARCH_BUDGET',
            value: '30000',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'AGENT_DEEP_RESEARCH_BUDGET',
              category: 'agent',
              dataType: 'integer',
              uiControl: 'number',
              isSensitive: false,
              isRequired: false,
              isEditable: false,
              options: [],
              validation: {},
              displayOrder: 2,
            },
          },
          {
            key: 'AGENT_EVENT_MONITOR_ENABLED',
            value: 'false',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'AGENT_EVENT_MONITOR_ENABLED',
              category: 'agent',
              dataType: 'boolean',
              uiControl: 'switch',
              isSensitive: false,
              isRequired: false,
              isEditable: false,
              options: [],
              validation: {},
              displayOrder: 3,
            },
          },
        ],
      },
    }));

    render(<SettingsPage />);

    expect(screen.getByText('AGENT_ORCHESTRATOR_TIMEOUT_S')).toBeInTheDocument();
    expect(screen.queryByText('AGENT_DEEP_RESEARCH_BUDGET')).not.toBeInTheDocument();
    expect(screen.queryByText('AGENT_EVENT_MONITOR_ENABLED')).not.toBeInTheDocument();
  });

  it('reset button semantic: discards local changes without network request', () => {
    // Simulate user has unsaved drafts
    const dirtyState = buildSystemConfigState({
      hasDirty: true,
      dirtyCount: 2,
    });

    useSystemConfigMock.mockReturnValue(dirtyState);

    render(<SettingsPage />);

    // Clear initial useEffect load call
    vi.clearAllMocks();

    // Click reset button
    fireEvent.click(screen.getByRole('button', { name: '重置' }));

    // Verify semantic: reset should only discard local changes
    // It should NOT trigger a network load
    expect(resetDraft).toHaveBeenCalledTimes(1);
    expect(load).not.toHaveBeenCalled();
    expect(save).not.toHaveBeenCalled();
  });

  it('keeps base raw fields behind disclosure while keeping smart import visible', () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({ activeCategory: 'base' }));

    render(<SettingsPage />);

    expect(screen.getByRole('button', { name: 'merge stock list' })).toBeInTheDocument();
    const summary = screen.getByText('展开原始字段与兼容键');
    const disclosure = summary.closest('details');

    expect(disclosure).not.toBeNull();
    expect(disclosure).not.toHaveAttribute('open');

    fireEvent.click(summary.closest('summary') ?? summary);

    expect(disclosure).toHaveAttribute('open');
    expect(screen.getByText('STOCK_LIST')).toBeInTheDocument();
  });

  it('refreshes server state after intelligent import merges stock list', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({ activeCategory: 'base' }));

    render(<SettingsPage />);

    fireEvent.click(screen.getByRole('button', { name: 'merge stock list' }));

    expect(saveExternalItems).toHaveBeenCalledWith([{ key: 'STOCK_LIST', value: 'SZ000001,SZ000002' }], '自选股配置已更新');
    expect(load).toHaveBeenCalledTimes(1);
  });

  it('refreshes server state after llm channel editor saves', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({ activeCategory: 'ai_model' }));

    render(<SettingsPage />);

    expect(screen.queryByRole('button', { name: 'save llm channels' })).toBeNull();
    await openAdvancedConfigDrawer();
    fireEvent.click(screen.getByRole('button', { name: 'save llm channels' }));

    expect(saveExternalItems).toHaveBeenCalledWith([{ key: 'LLM_CHANNELS', value: 'primary,backup' }], '渠道配置已保存');
    expect(load).toHaveBeenCalledTimes(1);
  });

  it('enables primary AI gateway selector when one configured provider is detected', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('AIHUBMIX_KEY', 'masked-token'),
          buildAiConfigItem('LLM_CHANNELS', ''),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', ''),
          buildAiConfigItem('AI_PRIMARY_MODEL', ''),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });
    const combos = within(aiSection).getAllByRole('combobox');

    const primaryGateway = combos[0] as HTMLSelectElement;
    const backupGateway = combos[1] as HTMLSelectElement;

    expect(primaryGateway).not.toBeDisabled();
    expect(primaryGateway.querySelector('option[value="aihubmix"]')).not.toBeNull();
    expect(backupGateway).toBeDisabled();
    expect(screen.getByText('备用路由需要至少两个已配置 AI Provider。')).toBeInTheDocument();
  });

  it('treats AIHUBMIX_API_KEY as credential-ready for gateway selection', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('AIHUBMIX_API_KEY', 'masked-token'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', ''),
          buildAiConfigItem('AI_PRIMARY_MODEL', ''),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });
    const combos = within(aiSection).getAllByRole('combobox');
    const primaryGateway = combos[0] as HTMLSelectElement;

    expect(primaryGateway).not.toBeDisabled();
    expect(primaryGateway.querySelector('option[value="aihubmix"]')).not.toBeNull();
  });

  it('enables primary selector for GLM/Zhipu when direct API key is configured', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('ZHIPU_API_KEY', 'masked-token'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', ''),
          buildAiConfigItem('AI_PRIMARY_MODEL', ''),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });
    const combos = within(aiSection).getAllByRole('combobox');

    const primaryGateway = combos[0] as HTMLSelectElement;
    const backupGateway = combos[1] as HTMLSelectElement;

    expect(primaryGateway).not.toBeDisabled();
    expect(primaryGateway.querySelector('option[value="zhipu"]')).not.toBeNull();
    expect(backupGateway).toBeDisabled();
  });

  it('uses configured providers as the source of truth for gateway selector options', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('AIHUBMIX_KEY', 'masked-token'),
          buildAiConfigItem('GEMINI_API_KEY', 'masked-token'),
          buildAiConfigItem('LLM_CHANNELS', ''),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', ''),
          buildAiConfigItem('AI_PRIMARY_MODEL', ''),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });
    const combos = within(aiSection).getAllByRole('combobox');

    const primaryGateway = combos[0] as HTMLSelectElement;
    const backupGateway = combos[1] as HTMLSelectElement;

    expect(primaryGateway).not.toBeDisabled();
    expect(backupGateway).not.toBeDisabled();
    expect(primaryGateway.querySelector('option[value="aihubmix"]')).not.toBeNull();
    expect(primaryGateway.querySelector('option[value="gemini"]')).not.toBeNull();
    expect(backupGateway.querySelector('option[value="aihubmix"]')).not.toBeNull();
    expect(backupGateway.querySelector('option[value="gemini"]')).not.toBeNull();
    expect(screen.getAllByRole('option', { name: 'AIHubMix' }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('option', { name: 'Gemini' }).length).toBeGreaterThan(0);
  });

  it('does not backfill phantom Zhipu glm-5 from stale saved models when only glm-4 is declared', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('LLM_CHANNELS', 'zhipu'),
          buildAiConfigItem('LLM_ZHIPU_API_KEY', 'masked-zhipu-key'),
          buildAiConfigItem('LLM_ZHIPU_ENABLED', 'true'),
          buildAiConfigItem('LLM_ZHIPU_MODELS', 'glm-4'),
          buildAiConfigItem('LITELLM_FALLBACK_MODELS', 'zhipu/glm-5'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'zhipu'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'zhipu/glm-5'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });

    fireEvent.click(within(aiSection).getAllByRole('button', { name: '显式模型 ID' })[0] as HTMLButtonElement);
    fireEvent.click(within(aiSection).getAllByRole('button', { name: '预设选择' })[0] as HTMLButtonElement);

    const combos = within(aiSection).getAllByRole('combobox');
    const primaryModel = combos[1] as HTMLSelectElement;
    expect(primaryModel.querySelector('option[value="glm-4"]')).not.toBeNull();
    expect(primaryModel.querySelector('option[value="zhipu/glm-5"]')).toBeNull();
  });

  it('saves GLM/Zhipu main route with bare glm-4 when advanced channel explicitly declares glm-4', async () => {
    saveExternalItems.mockResolvedValue(undefined);
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('LLM_CHANNELS', 'zhipu'),
          buildAiConfigItem('LLM_ZHIPU_API_KEY', 'masked-zhipu-key'),
          buildAiConfigItem('LLM_ZHIPU_ENABLED', 'true'),
          buildAiConfigItem('LLM_ZHIPU_MODELS', 'glm-4'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', ''),
          buildAiConfigItem('AI_PRIMARY_MODEL', ''),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
          buildAiConfigItem('LITELLM_MODEL', ''),
          buildAiConfigItem('LITELLM_FALLBACK_MODELS', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });

    let combos = within(aiSection).getAllByRole('combobox');
    fireEvent.change(combos[0] as HTMLSelectElement, { target: { value: 'zhipu' } });
    fireEvent.click(within(aiSection).getAllByRole('button', { name: '显式模型 ID' })[0] as HTMLButtonElement);
    fireEvent.click(within(aiSection).getAllByRole('button', { name: '预设选择' })[0] as HTMLButtonElement);
    combos = within(aiSection).getAllByRole('combobox');
    fireEvent.change(combos[1] as HTMLSelectElement, { target: { value: 'glm-4' } });
    fireEvent.click(within(aiSection).getByRole('button', { name: '保存优先顺序' }));

    await waitFor(() => {
      expect(saveExternalItems).toHaveBeenCalledWith(expect.arrayContaining([
        { key: 'AI_PRIMARY_GATEWAY', value: 'zhipu' },
        { key: 'AI_PRIMARY_MODEL', value: 'glm-4' },
        { key: 'LITELLM_MODEL', value: 'glm-4' },
      ]), expect.stringContaining('主路由'));
    });
  });

  it('does not enable AI gateway selectors from legacy LLM_CHANNELS alone', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('LLM_CHANNELS', 'gemini,aihubmix'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', ''),
          buildAiConfigItem('AI_PRIMARY_MODEL', ''),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });
    const combos = within(aiSection).getAllByRole('combobox');

    const primaryGateway = combos[0] as HTMLSelectElement;
    const backupGateway = combos[1] as HTMLSelectElement;

    expect(primaryGateway).toBeDisabled();
    expect(backupGateway).toBeDisabled();
    expect(within(aiSection).getByText('无主路由网关。请先配置 AI Provider 凭据。')).toBeInTheDocument();
    expect(within(aiSection).getByText('备用路由需要至少两个已配置 AI Provider。')).toBeInTheDocument();
  });

  it('saves primary-only AI route and keeps legacy channel list stable', async () => {
    saveExternalItems.mockResolvedValue(undefined);
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('GEMINI_API_KEY', 'masked-token'),
          buildAiConfigItem('LLM_CHANNELS', 'legacy'),
          buildAiConfigItem('LITELLM_MODEL', ''),
          buildAiConfigItem('LITELLM_FALLBACK_MODELS', 'legacy/fallback'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', ''),
          buildAiConfigItem('AI_PRIMARY_MODEL', ''),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });
    const combos = within(aiSection).getAllByRole('combobox');
    const primaryGateway = combos[0] as HTMLSelectElement;

    fireEvent.change(primaryGateway, { target: { value: 'gemini' } });
    fireEvent.click(within(aiSection).getByRole('button', { name: '保存优先顺序' }));

    await waitFor(() => {
      expect(saveExternalItems).toHaveBeenCalledWith([
        { key: 'AI_PRIMARY_GATEWAY', value: 'gemini' },
        { key: 'AI_PRIMARY_MODEL', value: 'gemini/gemini-2.5-flash' },
        { key: 'AI_BACKUP_GATEWAY', value: '' },
        { key: 'AI_BACKUP_MODEL', value: '' },
        { key: 'LLM_CHANNELS', value: 'legacy' },
        { key: 'LITELLM_MODEL', value: 'gemini/gemini-2.5-flash' },
        { key: 'LITELLM_FALLBACK_MODELS', value: '' },
      ], expect.stringContaining('主路由'));
    });
  });

  it('saves primary AIHubMix route with a manual model id', async () => {
    saveExternalItems.mockResolvedValue(undefined);
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('AIHUBMIX_KEY', 'masked-token'),
          buildAiConfigItem('LLM_CHANNELS', 'legacy'),
          buildAiConfigItem('LITELLM_MODEL', ''),
          buildAiConfigItem('LITELLM_FALLBACK_MODELS', ''),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', ''),
          buildAiConfigItem('AI_PRIMARY_MODEL', ''),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });
    const combos = within(aiSection).getAllByRole('combobox');
    const primaryGateway = combos[0] as HTMLSelectElement;

    fireEvent.change(primaryGateway, { target: { value: 'aihubmix' } });
    fireEvent.click(within(aiSection).getAllByRole('button', { name: '显式模型 ID' })[0] as HTMLButtonElement);
    const customButtons = within(aiSection).getAllByRole('button', { name: '自定义 ID' });
    fireEvent.click(customButtons[0] as HTMLButtonElement);
    const primaryCustomModelInput = within(aiSection).getByLabelText('自定义模型 ID') as HTMLInputElement;
    fireEvent.change(primaryCustomModelInput, { target: { value: 'openai/gpt-4.1-free' } });
    fireEvent.click(within(aiSection).getByRole('button', { name: '保存优先顺序' }));

    await waitFor(() => {
      expect(saveExternalItems).toHaveBeenCalledWith([
        { key: 'AI_PRIMARY_GATEWAY', value: 'aihubmix' },
        { key: 'AI_PRIMARY_MODEL', value: 'openai/gpt-4.1-free' },
        { key: 'AI_BACKUP_GATEWAY', value: '' },
        { key: 'AI_BACKUP_MODEL', value: '' },
        { key: 'LLM_CHANNELS', value: 'legacy' },
        { key: 'LITELLM_MODEL', value: 'openai/gpt-4.1-free' },
        { key: 'LITELLM_FALLBACK_MODELS', value: '' },
      ], expect.stringContaining('主路由'));
    });
  });

  it('does not require preset coverage for AIHubMix manual model ids', async () => {
    saveExternalItems.mockResolvedValue(undefined);
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('AIHUBMIX_KEY', 'masked-token'),
          buildAiConfigItem('LLM_CHANNELS', 'legacy'),
          buildAiConfigItem('LITELLM_MODEL', ''),
          buildAiConfigItem('LITELLM_FALLBACK_MODELS', ''),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', ''),
          buildAiConfigItem('AI_PRIMARY_MODEL', ''),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });
    const combos = within(aiSection).getAllByRole('combobox');
    const primaryGateway = combos[0] as HTMLSelectElement;

    fireEvent.change(primaryGateway, { target: { value: 'aihubmix' } });
    fireEvent.click(within(aiSection).getAllByRole('button', { name: '显式模型 ID' })[0] as HTMLButtonElement);
    const customButtons = within(aiSection).getAllByRole('button', { name: '自定义 ID' });
    fireEvent.click(customButtons[0] as HTMLButtonElement);
    const primaryCustomModelInput = within(aiSection).getByLabelText('自定义模型 ID') as HTMLInputElement;
    fireEvent.change(primaryCustomModelInput, { target: { value: 'openai/gpt-4.1-future' } });
    fireEvent.click(within(aiSection).getByRole('button', { name: '保存优先顺序' }));

    await waitFor(() => {
      expect(saveExternalItems).toHaveBeenCalledWith(expect.arrayContaining([
        { key: 'AI_PRIMARY_GATEWAY', value: 'aihubmix' },
        { key: 'AI_PRIMARY_MODEL', value: 'openai/gpt-4.1-future' },
      ]), expect.stringContaining('主路由'));
    });
  });

  it('clears backup gateway/model draft state via visible clear action', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('AIHUBMIX_KEY', 'masked-token'),
          buildAiConfigItem('GEMINI_API_KEY', 'masked-token'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'aihubmix'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'openai/gpt-4.1-mini'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });
    let combos = within(aiSection).getAllByRole('combobox');
    const backupGateway = combos[1] as HTMLSelectElement;
    fireEvent.change(backupGateway, { target: { value: 'gemini' } });
    fireEvent.click(within(aiSection).getAllByRole('button', { name: '显式模型 ID' })[1] as HTMLButtonElement);
    combos = within(aiSection).getAllByRole('combobox');
    const backupModel = combos[2] as HTMLSelectElement;
    fireEvent.change(backupModel, { target: { value: 'gemini/gemini-2.5-flash' } });

    fireEvent.click(within(aiSection).getByRole('button', { name: '清空备用路由' }));

    expect((within(aiSection).getAllByRole('combobox')[1] as HTMLSelectElement).value).toBe('');
  });

  it('saves primary-only route after clearing backup and clears legacy fallback models', async () => {
    saveExternalItems.mockResolvedValue(undefined);
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('GEMINI_API_KEY', 'masked-token'),
          buildAiConfigItem('AIHUBMIX_KEY', 'masked-token'),
          buildAiConfigItem('LLM_CHANNELS', 'legacy'),
          buildAiConfigItem('LITELLM_MODEL', 'gemini/gemini-2.5-flash'),
          buildAiConfigItem('LITELLM_FALLBACK_MODELS', 'openai/gpt-4.1-mini'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'gemini'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'gemini/gemini-2.5-flash'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', 'aihubmix'),
          buildAiConfigItem('AI_BACKUP_MODEL', 'openai/gpt-4.1-mini'),
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });

    fireEvent.click(within(aiSection).getByRole('button', { name: '清空备用路由' }));
    fireEvent.click(within(aiSection).getByRole('button', { name: '保存优先顺序' }));

    await waitFor(() => {
      expect(saveExternalItems).toHaveBeenCalledWith(expect.arrayContaining([
        { key: 'AI_PRIMARY_GATEWAY', value: 'gemini' },
        { key: 'AI_PRIMARY_MODEL', value: 'gemini/gemini-2.5-flash' },
        { key: 'AI_BACKUP_GATEWAY', value: '' },
        { key: 'AI_BACKUP_MODEL', value: '' },
        { key: 'LITELLM_FALLBACK_MODELS', value: '' },
      ]), expect.stringContaining('主路由'));
    });
  });

  it('shows inline pre-save guidance when backup model is not declared by enabled channels', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('AIHUBMIX_KEY', 'masked-token'),
          buildAiConfigItem('LLM_GEMINI_API_KEY', 'masked-token'),
          buildAiConfigItem('LLM_CHANNELS', 'gemini,aihubmix'),
          buildAiConfigItem('LLM_GEMINI_ENABLED', 'true'),
          buildAiConfigItem('LLM_GEMINI_MODELS', 'gemini/gemini-2.5-flash'),
          buildAiConfigItem('LLM_AIHUBMIX_ENABLED', 'true'),
          buildAiConfigItem('LLM_AIHUBMIX_MODELS', 'openai/gpt-4.1-mini'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'aihubmix'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'openai/gpt-4.1-mini'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });
    let combos = within(aiSection).getAllByRole('combobox');
    const backupGateway = combos[1] as HTMLSelectElement;
    fireEvent.change(backupGateway, { target: { value: 'gemini' } });
    fireEvent.click(within(aiSection).getAllByRole('button', { name: '显式模型 ID' })[1] as HTMLButtonElement);
    combos = within(aiSection).getAllByRole('combobox');
    const backupModel = combos[2] as HTMLSelectElement;
    fireEvent.change(backupModel, { target: { value: 'gemini/gemini-3-flash-preview' } });

    expect(screen.getByText(/未在已启用的 Gemini 渠道模型声明中找到/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '前往配置渠道模型' })).toBeInTheDocument();
    expect(within(aiSection).getByRole('button', { name: '保存优先顺序' })).toBeDisabled();
  });

  it('allows Gemini backup compatibility with direct Gemini API key only', async () => {
    saveExternalItems.mockResolvedValue(undefined);
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('AIHUBMIX_KEY', 'masked-token'),
          buildAiConfigItem('GEMINI_API_KEY', 'masked-token'),
          buildAiConfigItem('LLM_CHANNELS', 'aihubmix'),
          buildAiConfigItem('LLM_AIHUBMIX_ENABLED', 'true'),
          buildAiConfigItem('LLM_AIHUBMIX_MODELS', 'openai/gpt-4.1-mini'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'aihubmix'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'openai/gpt-4.1-mini'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
          buildAiConfigItem('LITELLM_FALLBACK_MODELS', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });
    let combos = within(aiSection).getAllByRole('combobox');
    const backupGateway = combos[1] as HTMLSelectElement;
    fireEvent.change(backupGateway, { target: { value: 'gemini' } });
    fireEvent.click(within(aiSection).getAllByRole('button', { name: '显式模型 ID' })[1] as HTMLButtonElement);
    combos = within(aiSection).getAllByRole('combobox');
    const backupModel = combos[2] as HTMLSelectElement;
    fireEvent.change(backupModel, { target: { value: 'gemini/gemini-3-flash-preview' } });

    expect(screen.queryByText(/未在已启用的 Gemini 渠道模型声明中找到/)).toBeNull();
    expect(within(aiSection).getByRole('button', { name: '保存优先顺序' })).not.toBeDisabled();
    fireEvent.click(within(aiSection).getByRole('button', { name: '保存优先顺序' }));

    await waitFor(() => {
      expect(saveExternalItems).toHaveBeenCalledWith(expect.arrayContaining([
        { key: 'AI_BACKUP_GATEWAY', value: 'gemini' },
        { key: 'AI_BACKUP_MODEL', value: 'gemini/gemini-3-flash-preview' },
      ]), expect.stringContaining('备用路由'));
    });
  });

  it('saves backup route when backup model is declared by enabled channels', async () => {
    saveExternalItems.mockResolvedValue(undefined);
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('AIHUBMIX_KEY', 'masked-token'),
          buildAiConfigItem('GEMINI_API_KEY', 'masked-token'),
          buildAiConfigItem('LLM_CHANNELS', 'gemini,aihubmix'),
          buildAiConfigItem('LLM_GEMINI_ENABLED', 'true'),
          buildAiConfigItem('LLM_GEMINI_MODELS', 'gemini/gemini-2.5-flash'),
          buildAiConfigItem('LLM_AIHUBMIX_ENABLED', 'true'),
          buildAiConfigItem('LLM_AIHUBMIX_MODELS', 'openai/gpt-4.1-mini'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'aihubmix'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'openai/gpt-4.1-mini'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
          buildAiConfigItem('LITELLM_FALLBACK_MODELS', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });
    let combos = within(aiSection).getAllByRole('combobox');
    const backupGateway = combos[1] as HTMLSelectElement;
    fireEvent.change(backupGateway, { target: { value: 'gemini' } });
    fireEvent.click(within(aiSection).getAllByRole('button', { name: '显式模型 ID' })[1] as HTMLButtonElement);
    combos = within(aiSection).getAllByRole('combobox');
    const backupModel = combos[2] as HTMLSelectElement;
    fireEvent.change(backupModel, { target: { value: 'gemini/gemini-2.5-flash' } });
    fireEvent.click(within(aiSection).getByRole('button', { name: '保存优先顺序' }));

    await waitFor(() => {
      expect(saveExternalItems).toHaveBeenCalledWith(expect.arrayContaining([
        { key: 'AI_BACKUP_GATEWAY', value: 'gemini' },
        { key: 'AI_BACKUP_MODEL', value: 'gemini/gemini-2.5-flash' },
        { key: 'LITELLM_FALLBACK_MODELS', value: 'gemini/gemini-2.5-flash' },
      ]), expect.stringContaining('备用路由'));
    });
  });

  it('overwrites stale legacy fallback models when saving a new backup route', async () => {
    saveExternalItems.mockResolvedValue(undefined);
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('AIHUBMIX_KEY', 'masked-token'),
          buildAiConfigItem('GEMINI_API_KEY', 'masked-token'),
          buildAiConfigItem('LLM_CHANNELS', 'legacy'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'aihubmix'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'openai/gpt-4.1-mini'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
          buildAiConfigItem('LITELLM_FALLBACK_MODELS', 'legacy/invalid,legacy/old'),
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });
    let combos = within(aiSection).getAllByRole('combobox');
    const backupGateway = combos[1] as HTMLSelectElement;
    fireEvent.change(backupGateway, { target: { value: 'gemini' } });
    fireEvent.click(within(aiSection).getAllByRole('button', { name: '显式模型 ID' })[1] as HTMLButtonElement);
    combos = within(aiSection).getAllByRole('combobox');
    const backupModel = combos[2] as HTMLSelectElement;
    fireEvent.change(backupModel, { target: { value: 'gemini/gemini-2.5-flash' } });
    fireEvent.click(within(aiSection).getByRole('button', { name: '保存优先顺序' }));

    await waitFor(() => {
      expect(saveExternalItems).toHaveBeenCalledWith(expect.arrayContaining([
        { key: 'LITELLM_FALLBACK_MODELS', value: 'gemini/gemini-2.5-flash' },
      ]), expect.stringContaining('备用路由'));
    });
  });

  it('shows visible route-to-channel configuration entry in AI routing section', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({ activeCategory: 'ai_model' }));
    render(<SettingsPage />);
    await openAiRoutingDrawer();
    expect(screen.getByRole('dialog', { name: '任务路由编辑' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '编辑任务路由' })).toBeInTheDocument();
    expect(screen.getByText('Provider 快速配置')).toBeInTheDocument();
    expect(screen.getByText('1. 任务路由')).toBeInTheDocument();
    expect(screen.getByText('2. Provider Library')).toBeInTheDocument();
    expect(screen.getByText('3. 高级配置（可选）')).toBeInTheDocument();
    expect(screen.getByText('高级渠道配置')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '打开高级设置' })).toBeInTheDocument();
    expect(screen.getByTestId('ai-task-row-analysis')).toBeInTheDocument();
    expect(screen.getByTestId('ai-task-row-stock_chat')).toBeInTheDocument();
    expect(screen.getByTestId('ai-task-row-backtest')).toBeInTheDocument();
    expect(screen.getAllByText('GLM / Zhipu').length).toBeGreaterThan(0);
  });

  it('renders a compact effective AI summary and removes the duplicate task-model recap section', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('GEMINI_API_KEY', 'masked-token'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'gemini'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'gemini/gemini-2.5-flash'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    expect(screen.queryByRole('heading', { name: '当前生效 AI 配置' })).toBeNull();
    const aiSection = screen.getByRole('heading', { name: '任务路由' }).closest('section');
    expect(aiSection).not.toBeNull();
    const aiSummary = within(aiSection as HTMLElement).getByTestId('ai-effective-summary');
    expect(within(aiSummary).getByTestId('ai-task-row-analysis')).toBeInTheDocument();
    expect(within(aiSummary).getByTestId('ai-task-row-stock_chat')).toBeInTheDocument();
    expect(within(aiSummary).getByTestId('ai-task-row-backtest')).toBeInTheDocument();
    expect(within(aiSummary).getAllByText('Analysis').length).toBeGreaterThan(0);
    expect(within(aiSummary).getByText('Stock Chat')).toBeInTheDocument();
    expect(within(aiSummary).getByText('Backtesting')).toBeInTheDocument();
    expect(within(aiSummary).getAllByText(/Gemini \/ gemini\/gemini-2\.5-flash/).length).toBeGreaterThan(0);
    expect(screen.queryByText('按任务配置模型')).toBeNull();
  });

  it('shows the inherited backtest route summary only once in the compact AI summary', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('GEMINI_API_KEY', 'masked-token'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'gemini'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'gemini/gemini-2.5-flash'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
          buildAiConfigItem('BACKTEST_LITELLM_MODEL', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    const aiSection = screen.getByRole('heading', { name: '任务路由' }).closest('section');
    expect(aiSection).not.toBeNull();

    expect(
      within(aiSection as HTMLElement).getAllByText(/回测路由：当前继承 Analysis 路由/).length,
    ).toBe(1);
  });

  it('splits data settings into Data Routing and Data Source Library', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'data_source',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        data_source: [
          {
            key: 'REALTIME_SOURCE_PRIORITY',
            value: 'finnhub,yahoo',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'REALTIME_SOURCE_PRIORITY',
              category: 'data_source',
              dataType: 'string',
              uiControl: 'text',
              isSensitive: false,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 1,
            },
          },
          {
            key: 'FINNHUB_API_KEY',
            value: 'masked-finnhub-token',
            rawValueExists: true,
            isMasked: false,
            schema: {
              key: 'FINNHUB_API_KEY',
              category: 'data_source',
              dataType: 'string',
              uiControl: 'text',
              isSensitive: true,
              isRequired: false,
              isEditable: true,
              options: [],
              validation: {},
              displayOrder: 2,
            },
          },
        ],
      },
    }));

    render(<SettingsPage />);

    const dataSection = screen.getByRole('heading', { name: '数据源配置' }).closest('section');
    expect(dataSection).not.toBeNull();
    expect(within(dataSection as HTMLElement).getByText('1. 数据路由')).toBeInTheDocument();
    expect(within(dataSection as HTMLElement).getByText('2. 数据源库')).toBeInTheDocument();
    expect(within(dataSection as HTMLElement).getByText('行情数据')).toBeInTheDocument();
    expect(within(dataSection as HTMLElement).getByText(/Finnhub -> Yahoo/)).toBeInTheDocument();
    const finnhubCard = within(dataSection as HTMLElement).getByTestId('data-source-card-finnhub');
    expect(within(finnhubCard).getByText('Finnhub')).toBeInTheDocument();
    expect(within(finnhubCard).getByText('行情')).toBeInTheDocument();
    expect(within(finnhubCard).getByText('基本面')).toBeInTheDocument();
    expect(within(finnhubCard).getByText('新闻')).toBeInTheDocument();
    expect(within(finnhubCard).getByText('已配置待验证')).toBeInTheDocument();
    expect(within(finnhubCard).getByText('状态检查：已配置，未做连通性验证')).toBeInTheDocument();
    const yahooCard = within(dataSection as HTMLElement).getByTestId('data-source-card-yahoo');
    expect(within(yahooCard).getByText('内置源')).toBeInTheDocument();
    expect(within(yahooCard).getByText('行情')).toBeInTheDocument();
    expect(within(yahooCard).getByText('基本面')).toBeInTheDocument();
    expect(within(yahooCard).getAllByText('状态检查：内置源无需验证').length).toBeGreaterThan(0);
    expect(within(dataSection as HTMLElement).getAllByRole('combobox').length).toBeGreaterThan(0);
    expect(within(dataSection as HTMLElement).getAllByRole('button', { name: '保存优先顺序' }).length).toBeGreaterThan(0);
  });

  it('shows the runtime summary visibility title only once in the advanced domain section', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'system',
    }));

    render(<SettingsPage />);

    expect(await screen.findByRole('heading', { name: '首页运行时执行摘要可见性' })).toBeInTheDocument();
    expect(screen.getAllByText('首页运行时执行摘要可见性').length).toBe(1);
  });

  it('creates a custom data source and exposes it only in the matching routing selector', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'data_source',
    }));

    render(<SettingsPage />);

    const dataSection = screen.getByRole('heading', { name: '数据源配置' }).closest('section');
    expect(dataSection).not.toBeNull();

    fireEvent.click(within(dataSection as HTMLElement).getByRole('button', { name: '添加数据源' }));
    const drawer = await screen.findByRole('dialog', { name: '注册数据源' });

    fireEvent.change(within(drawer).getByLabelText('显示名称'), { target: { value: 'Demo News API' } });
    fireEvent.change(within(drawer).getByLabelText('API Key / 凭据'), { target: { value: 'demo-news-key' } });
    fireEvent.change(within(drawer).getByLabelText('Base URL'), { target: { value: 'https://demo.example.com/v1' } });
    fireEvent.click(within(drawer).getByRole('button', { name: '新闻' }));
    fireEvent.click(within(drawer).getByRole('button', { name: '创建并保存' }));

    await waitFor(() => {
      expect(saveExternalItems).toHaveBeenCalledWith(
        expect.arrayContaining([
          expect.objectContaining({
            key: 'CUSTOM_DATA_SOURCE_LIBRARY',
            value: expect.stringContaining('"name":"Demo News API"'),
          }),
        ]),
        expect.stringContaining('数据源库已更新'),
      );
    });
    expect(saveExternalItems).toHaveBeenCalledWith(
      expect.arrayContaining([
        expect.objectContaining({
          key: 'CUSTOM_DATA_SOURCE_LIBRARY',
          value: expect.stringContaining('"credentialSchema":"single_key"'),
        }),
      ]),
      expect.any(String),
    );

    const customCard = within(dataSection as HTMLElement).getByTestId('data-source-card-demo_news_api');
    expect(within(customCard).getByText('自定义源')).toBeInTheDocument();
    expect(within(customCard).getByText('新闻')).toBeInTheDocument();
    expect(within(customCard).getByText('已配置待验证')).toBeInTheDocument();

    const newsGroup = within(dataSection as HTMLElement).getByText('新闻数据').closest('div.flex.items-start');
    expect(newsGroup).not.toBeNull();
    expect(within(newsGroup as HTMLElement).getAllByRole('option', { name: /Demo News Api/i }).length).toBeGreaterThan(0);

    const marketGroup = within(dataSection as HTMLElement).getByText('行情数据').closest('div.flex.items-start');
    expect(marketGroup).not.toBeNull();
    expect(within(marketGroup as HTMLElement).queryAllByRole('option', { name: /Demo News Api/i }).length).toBe(0);
  });

  it('supports custom key-secret data sources and persists both credentials', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'data_source',
    }));

    render(<SettingsPage />);

    const dataSection = screen.getByRole('heading', { name: '数据源配置' }).closest('section');
    expect(dataSection).not.toBeNull();

    fireEvent.click(within(dataSection as HTMLElement).getByRole('button', { name: '添加数据源' }));
    const drawer = await screen.findByRole('dialog', { name: '注册数据源' });

    fireEvent.click(within(drawer).getByRole('button', { name: /Key \+ Secret/ }));
    fireEvent.change(within(drawer).getByLabelText('显示名称'), { target: { value: 'Demo Market Broker' } });
    fireEvent.change(within(drawer).getByLabelText('API Key / 凭据'), { target: { value: 'demo-market-key' } });
    fireEvent.change(within(drawer).getByLabelText('Secret Key'), { target: { value: 'demo-market-secret' } });
    fireEvent.click(within(drawer).getByRole('button', { name: '行情' }));
    fireEvent.click(within(drawer).getByRole('button', { name: '创建并保存' }));

    await waitFor(() => {
      expect(saveExternalItems).toHaveBeenCalledWith(
        expect.arrayContaining([
          expect.objectContaining({
            key: 'CUSTOM_DATA_SOURCE_LIBRARY',
            value: expect.stringContaining('"credentialSchema":"key_secret"'),
          }),
        ]),
        expect.stringContaining('数据源库已更新'),
      );
    });
    expect(saveExternalItems).toHaveBeenCalledWith(
      expect.arrayContaining([
        expect.objectContaining({
          key: 'CUSTOM_DATA_SOURCE_LIBRARY',
          value: expect.stringContaining('"secret":"demo-market-secret"'),
        }),
      ]),
      expect.any(String),
    );
  });

  it('manages Alpaca built-in credentials with key-secret plus feed fields', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'data_source',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        data_source: [
          buildDataSourceConfigItem('REALTIME_SOURCE_PRIORITY', 'alpaca,yahoo'),
          buildDataSourceConfigItem('ALPACA_API_KEY_ID', ''),
          buildDataSourceConfigItem('ALPACA_API_SECRET_KEY', ''),
          buildDataSourceConfigItem('ALPACA_DATA_FEED', 'iex'),
        ],
      },
    }));

    render(<SettingsPage />);

    const dataSection = screen.getByRole('heading', { name: '数据源配置' }).closest('section');
    expect(dataSection).not.toBeNull();
    const alpacaCard = within(dataSection as HTMLElement).getByTestId('data-source-card-alpaca');

    fireEvent.click(within(alpacaCard).getByRole('button', { name: '管理' }));
    const drawer = await screen.findByRole('dialog', { name: 'Alpaca 数据源管理' });

    fireEvent.change(within(drawer).getByLabelText(/Alpaca Key ID/i), { target: { value: 'alpaca-key-id' } });
    fireEvent.change(within(drawer).getByLabelText(/Secret Key/i), { target: { value: 'alpaca-secret-key' } });
    fireEvent.change(within(drawer).getByLabelText(/Feed/i), { target: { value: 'sip' } });
    fireEvent.click(within(drawer).getByRole('button', { name: '保存更改' }));

    await waitFor(() => {
      expect(saveExternalItems).toHaveBeenCalledWith([
        { key: 'ALPACA_API_KEY_ID', value: 'alpaca-key-id' },
        { key: 'ALPACA_API_SECRET_KEY', value: 'alpaca-secret-key' },
        { key: 'ALPACA_DATA_FEED', value: 'sip' },
      ], '数据源库已更新');
    });
  });

  it('stores Twelve Data credentials in the singular key when one token is provided', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'data_source',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        data_source: [
          buildDataSourceConfigItem('REALTIME_SOURCE_PRIORITY', 'twelve_data,yahoo'),
          buildDataSourceConfigItem('TWELVE_DATA_API_KEY', ''),
          buildDataSourceConfigItem('TWELVE_DATA_API_KEYS', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    const dataSection = screen.getByRole('heading', { name: '数据源配置' }).closest('section');
    expect(dataSection).not.toBeNull();
    const twelveDataCard = within(dataSection as HTMLElement).getByTestId('data-source-card-twelve_data');

    fireEvent.click(within(twelveDataCard).getByRole('button', { name: '管理' }));
    const drawer = await screen.findByRole('dialog', { name: 'Twelve Data 数据源管理' });

    fireEvent.change(within(drawer).getByLabelText('API Key / 凭据'), { target: { value: 'twelve-single-key' } });
    fireEvent.click(within(drawer).getByRole('button', { name: '保存更改' }));

    await waitFor(() => {
      expect(saveExternalItems).toHaveBeenCalledWith([
        { key: 'TWELVE_DATA_API_KEY', value: 'twelve-single-key' },
        { key: 'TWELVE_DATA_API_KEYS', value: '' },
      ], '数据源库已更新');
    });
  });

  it('stores Twelve Data credentials in the plural key when multiple tokens are provided', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'data_source',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        data_source: [
          buildDataSourceConfigItem('REALTIME_SOURCE_PRIORITY', 'twelve_data,yahoo'),
          buildDataSourceConfigItem('TWELVE_DATA_API_KEY', ''),
          buildDataSourceConfigItem('TWELVE_DATA_API_KEYS', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    const dataSection = screen.getByRole('heading', { name: '数据源配置' }).closest('section');
    expect(dataSection).not.toBeNull();
    const twelveDataCard = within(dataSection as HTMLElement).getByTestId('data-source-card-twelve_data');

    fireEvent.click(within(twelveDataCard).getByRole('button', { name: '管理' }));
    const drawer = await screen.findByRole('dialog', { name: 'Twelve Data 数据源管理' });

    fireEvent.change(within(drawer).getByLabelText('API Key / 凭据'), { target: { value: 'key-one,key-two' } });
    fireEvent.click(within(drawer).getByRole('button', { name: '保存更改' }));

    await waitFor(() => {
      expect(saveExternalItems).toHaveBeenCalledWith([
        { key: 'TWELVE_DATA_API_KEY', value: '' },
        { key: 'TWELVE_DATA_API_KEYS', value: 'key-one,key-two' },
      ], '数据源库已更新');
    });
  });

  it('shows quick-api status and advanced-channel count on provider cards', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('GEMINI_API_KEY', 'masked-token'),
          buildAiConfigItem('LLM_CHANNELS', 'aihubmix'),
          buildAiConfigItem('LLM_AIHUBMIX_PROTOCOL', 'openai'),
          buildAiConfigItem('LLM_AIHUBMIX_MODELS', 'openai/gpt-4.1-mini'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'gemini'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'gemini/gemini-2.5-flash'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    const providerSection = screen.getByTestId('ai-provider-quick-section');
    const geminiCard = within(providerSection).getByTestId('ai-provider-card-gemini');
    expect(within(geminiCard as HTMLElement).getByText(/Quick API/)).toBeInTheDocument();
    expect(within(geminiCard as HTMLElement).getByText(/高级渠道数: 0/)).toBeInTheDocument();

    const aihubmixCard = within(providerSection).getByTestId('ai-provider-card-aihubmix');
    expect(within(aihubmixCard as HTMLElement).getByText(/高级渠道数: 1/)).toBeInTheDocument();
  });

  it('shows provider-aware empty-state guidance when no advanced channel exists', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('ZHIPU_API_KEY', 'masked-token'),
          buildAiConfigItem('LLM_CHANNELS', 'aihubmix'),
          buildAiConfigItem('LLM_AIHUBMIX_PROTOCOL', 'openai'),
          buildAiConfigItem('LLM_AIHUBMIX_MODELS', 'openai/gpt-4.1-mini'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'zhipu'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'zhipu/glm-5'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));

    render(<SettingsPage />);
    fireEvent.click(screen.getByRole('button', { name: '管理 GLM / Zhipu 高级配置' }));

    await waitFor(() => {
      expect(screen.getByRole('dialog', { name: '高级 Provider / Channel 编辑' })).toBeInTheDocument();
    });
    const advancedDrawer = screen.getByRole('dialog', { name: '高级 Provider / Channel 编辑' });
    expect(within(advancedDrawer).getByText('GLM / Zhipu 的 Quick API 已配置，但尚未创建独立高级渠道。')).toBeInTheDocument();
    expect(within(advancedDrawer).getByRole('button', { name: '创建 GLM / Zhipu 高级渠道' })).toBeInTheDocument();
    expect(screen.getByTestId('llm-provider-scope')).toHaveTextContent('zhipu');
  });

  it('focuses provider advanced channel when it already exists', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('GEMINI_API_KEY', 'masked-token'),
          buildAiConfigItem('LLM_CHANNELS', 'gemini,aihubmix'),
          buildAiConfigItem('LLM_GEMINI_PROTOCOL', 'gemini'),
          buildAiConfigItem('LLM_GEMINI_MODELS', 'gemini/gemini-2.5-flash'),
          buildAiConfigItem('LLM_AIHUBMIX_PROTOCOL', 'openai'),
          buildAiConfigItem('LLM_AIHUBMIX_MODELS', 'openai/gpt-4.1-mini'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'gemini'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'gemini/gemini-2.5-flash'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));

    render(<SettingsPage />);
    fireEvent.click(screen.getByRole('button', { name: '管理 Gemini 高级配置' }));

    await waitFor(() => {
      expect(screen.getByRole('dialog', { name: '高级 Provider / Channel 编辑' })).toBeInTheDocument();
    });
    expect(screen.getAllByText('已定位到 Gemini 的高级渠道：gemini。').length).toBeGreaterThan(0);
    expect(screen.getByTestId('llm-provider-scope')).toHaveTextContent('gemini');
    expect(screen.getByTestId('llm-focus-channel')).toHaveTextContent('gemini');
  });

  it('renders provider quick test action and reports success', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('GEMINI_API_KEY', 'valid-gemini-key'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'gemini'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'gemini/gemini-2.5-flash'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));
    testLLMChannel.mockResolvedValue({
      success: true,
      message: 'ok',
      resolvedModel: 'gemini/gemini-2.5-flash',
      latencyMs: 86,
    });

    render(<SettingsPage />);

    await openQuickProviderDrawer('Gemini');
    const providerDrawer = screen.getByRole('dialog', { name: 'Gemini 快速配置' });
    fireEvent.click(within(providerDrawer).getByRole('button', { name: '测试连接' }));

    await waitFor(() => {
      expect(testLLMChannel).toHaveBeenCalledWith(expect.objectContaining({
        protocol: 'gemini',
        name: 'quick_gemini',
      }), expect.any(Object));
    });
    expect(within(providerDrawer).getByText(/连接成功/)).toBeInTheDocument();
    expect(within(providerDrawer).getByText(/86 ms/)).toBeInTheDocument();
  });

  it('shows provider quick test failure message when test fails', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('OPENAI_API_KEY', 'valid-openai-key'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'openai'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'openai/gpt-4.1-mini'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));
    testLLMChannel.mockResolvedValue({
      success: false,
      message: 'model is not available',
      error: 'model is not available',
      resolvedModel: null,
      latencyMs: null,
    });

    render(<SettingsPage />);

    await openQuickProviderDrawer('OpenAI');
    const providerDrawer = screen.getByRole('dialog', { name: 'OpenAI 快速配置' });
    fireEvent.click(within(providerDrawer).getByRole('button', { name: '测试连接' }));

    await waitFor(() => {
      expect(within(providerDrawer).getByText(/model is not available/)).toBeInTheDocument();
    });
  });

  it('prefers advanced channel model/protocol for Zhipu quick test when channel exists', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('ZHIPU_API_KEY', 'valid-zhipu-key'),
          buildAiConfigItem('LLM_CHANNELS', 'zhipu'),
          buildAiConfigItem('LLM_ZHIPU_PROTOCOL', 'openai'),
          buildAiConfigItem('LLM_ZHIPU_BASE_URL', 'https://open.bigmodel.cn/api/paas/v4'),
          buildAiConfigItem('LLM_ZHIPU_MODELS', 'glm-4-flash,glm-5'),
          buildAiConfigItem('LLM_ZHIPU_API_KEY', 'valid-zhipu-key'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'zhipu'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'zhipu/glm-5'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));
    testLLMChannel.mockResolvedValue({
      success: true,
      message: 'ok',
      resolvedModel: 'openai/glm-4-flash',
      latencyMs: 90,
    });

    render(<SettingsPage />);

    await openQuickProviderDrawer('GLM / Zhipu');
    const providerDrawer = screen.getByRole('dialog', { name: 'GLM / Zhipu 快速配置' });
    fireEvent.click(within(providerDrawer).getByRole('button', { name: '测试连接' }));

    await waitFor(() => {
      expect(testLLMChannel).toHaveBeenCalledWith(expect.objectContaining({
        name: 'zhipu',
        protocol: 'openai',
        baseUrl: 'https://open.bigmodel.cn/api/paas/v4',
        models: ['glm-4-flash'],
      }), expect.any(Object));
    });
  });

  it('adds advanced-testing guidance for Zhipu quick test failure without advanced channel', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('ZHIPU_API_KEY', 'valid-zhipu-key'),
          buildAiConfigItem('LLM_CHANNELS', ''),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'zhipu'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'zhipu/glm-5'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));
    testLLMChannel.mockResolvedValue({
      success: false,
      message: 'LLM channel returned empty content',
      error: 'Provider returned an empty response body',
      resolvedModel: 'openai/glm-5',
      latencyMs: 300,
    });

    render(<SettingsPage />);
    await openQuickProviderDrawer('GLM / Zhipu');
    const providerDrawer = screen.getByRole('dialog', { name: 'GLM / Zhipu 快速配置' });
    fireEvent.click(within(providerDrawer).getByRole('button', { name: '测试连接' }));

    await waitFor(() => {
      expect(within(providerDrawer).getByText(/自定义协议测试需经高级渠道/)).toBeInTheDocument();
    });
  });

  it('shows Stock Chat as shared when AGENT_LITELLM_MODEL is not set', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('GEMINI_API_KEY', 'masked-token'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'gemini'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'gemini/gemini-2.5-flash'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
        agent: [
          {
            ...buildAiConfigItem('AGENT_MODE', 'true'),
            schema: {
              ...buildAiConfigItem('AGENT_MODE', 'true').schema,
              category: 'agent',
            },
          },
          {
            ...buildAiConfigItem('AGENT_LITELLM_MODEL', ''),
            schema: {
              ...buildAiConfigItem('AGENT_LITELLM_MODEL', '').schema,
              category: 'agent',
            },
          },
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const stockTaskRow = screen.getByTestId('ai-task-row-stock_chat');
    expect(within(stockTaskRow).getByText('Stock Chat')).toBeInTheDocument();
    expect(within(stockTaskRow).getByText('与分析共用')).toBeInTheDocument();
    expect(within(stockTaskRow).getByText('Gemini / gemini/gemini-2.5-flash')).toBeInTheDocument();
    expect(within(stockTaskRow).getByText(/问股路由：继承分析主路由/)).toBeInTheDocument();
  });

  it('shows Stock Chat as dedicated when AGENT_LITELLM_MODEL is set', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('GEMINI_API_KEY', 'masked-token'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'gemini'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'gemini/gemini-2.5-flash'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
        agent: [
          {
            ...buildAiConfigItem('AGENT_MODE', 'true'),
            schema: {
              ...buildAiConfigItem('AGENT_MODE', 'true').schema,
              category: 'agent',
            },
          },
          {
            ...buildAiConfigItem('AGENT_LITELLM_MODEL', 'openai/gpt-4.1-mini'),
            schema: {
              ...buildAiConfigItem('AGENT_LITELLM_MODEL', 'openai/gpt-4.1-mini').schema,
              category: 'agent',
            },
          },
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const stockTaskRow = screen.getByTestId('ai-task-row-stock_chat');
    expect(within(stockTaskRow).getByText('Stock Chat')).toBeInTheDocument();
    expect(within(stockTaskRow).getByText('独立模型')).toBeInTheDocument();
    expect(within(stockTaskRow).getByText('OpenAI / openai/gpt-4.1-mini')).toBeInTheDocument();
    expect(within(stockTaskRow).getByText(/问股路由：使用独立模型（openai\/gpt-4\.1-mini）/)).toBeInTheDocument();
  });

  it('saves Stock Chat task override route independently', async () => {
    saveExternalItems.mockResolvedValue(undefined);
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('GEMINI_API_KEY', 'masked-token'),
          buildAiConfigItem('OPENAI_API_KEY', 'masked-token'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'gemini'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'gemini/gemini-2.5-flash'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
        agent: [
          {
            ...buildAiConfigItem('AGENT_MODE', 'true'),
            schema: {
              ...buildAiConfigItem('AGENT_MODE', 'true').schema,
              category: 'agent',
            },
          },
          {
            ...buildAiConfigItem('AGENT_LITELLM_MODEL', ''),
            schema: {
              ...buildAiConfigItem('AGENT_LITELLM_MODEL', '').schema,
              category: 'agent',
            },
          },
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });
    const stockTaskCard = within(aiSection).getByTestId('ai-task-card-stock_chat');

    fireEvent.click(within(stockTaskCard as HTMLElement).getByRole('button', { name: '独立覆盖' }));
    fireEvent.click(within(stockTaskCard as HTMLElement).getByRole('button', { name: '显式模型 ID' }));
    const taskCombos = within(stockTaskCard as HTMLElement).getAllByRole('combobox');
    fireEvent.change(taskCombos[0] as HTMLSelectElement, { target: { value: 'openai' } });
    fireEvent.change(taskCombos[1] as HTMLSelectElement, { target: { value: 'openai/gpt-4.1-mini' } });
    fireEvent.click(within(stockTaskCard as HTMLElement).getByRole('button', { name: '保存任务模型' }));

    await waitFor(() => {
      expect(saveExternalItems).toHaveBeenCalledWith([
        { key: 'AGENT_LITELLM_MODEL', value: 'openai/gpt-4.1-mini' },
      ], expect.stringContaining('OpenAI / openai/gpt-4.1-mini'));
    });
  });

  it('supports Backtesting inherit vs override save', async () => {
    saveExternalItems.mockResolvedValue(undefined);
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('GEMINI_API_KEY', 'masked-token'),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', 'gemini'),
          buildAiConfigItem('AI_PRIMARY_MODEL', 'gemini/gemini-2.5-flash'),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
          buildAiConfigItem('BACKTEST_LITELLM_MODEL', 'openai/gpt-4.1-mini'),
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });
    const backtestTaskCard = within(aiSection).getByTestId('ai-task-card-backtest');

    fireEvent.click(within(backtestTaskCard as HTMLElement).getByRole('button', { name: '继承 Analysis' }));
    fireEvent.click(within(backtestTaskCard as HTMLElement).getByRole('button', { name: '保存任务模型' }));

    await waitFor(() => {
      expect(saveExternalItems).toHaveBeenCalledWith([
        { key: 'BACKTEST_LITELLM_MODEL', value: '' },
      ], '已恢复继承 Analysis 主路由');
    });
  });

  it('blocks save with clear error when primary model is missing', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('GEMINI_API_KEY', 'masked-token'),
          buildAiConfigItem('LLM_CHANNELS', ''),
          buildAiConfigItem('LITELLM_MODEL', ''),
          buildAiConfigItem('LITELLM_FALLBACK_MODELS', ''),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', ''),
          buildAiConfigItem('AI_PRIMARY_MODEL', ''),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });
    const combos = within(aiSection).getAllByRole('combobox');

    fireEvent.change(combos[0] as HTMLSelectElement, { target: { value: 'gemini' } });
    fireEvent.click(within(aiSection).getAllByRole('button', { name: '显式模型 ID' })[0] as HTMLButtonElement);
    const customButtons = within(aiSection).getAllByRole('button', { name: '自定义 ID' });
    fireEvent.click(customButtons[0] as HTMLButtonElement);
    const primaryCustomModelInput = within(aiSection).getByLabelText('自定义模型 ID') as HTMLInputElement;
    fireEvent.change(primaryCustomModelInput, { target: { value: '' } });
    fireEvent.click(within(aiSection).getByRole('button', { name: '保存优先顺序' }));

    expect(saveExternalItems).not.toHaveBeenCalled();
    await waitFor(() => {
      expect(screen.getByText('主路由必须同时配置网关和模型。')).toBeInTheDocument();
    });
  });

  it('blocks save when backup route is partially filled', async () => {
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'ai_model',
      itemsByCategory: {
        ...buildSystemConfigState().itemsByCategory,
        ai_model: [
          buildAiConfigItem('AIHUBMIX_KEY', 'masked-token'),
          buildAiConfigItem('GEMINI_API_KEY', 'masked-token'),
          buildAiConfigItem('LLM_CHANNELS', ''),
          buildAiConfigItem('LITELLM_MODEL', ''),
          buildAiConfigItem('LITELLM_FALLBACK_MODELS', ''),
          buildAiConfigItem('AI_PRIMARY_GATEWAY', ''),
          buildAiConfigItem('AI_PRIMARY_MODEL', ''),
          buildAiConfigItem('AI_BACKUP_GATEWAY', ''),
          buildAiConfigItem('AI_BACKUP_MODEL', ''),
        ],
      },
    }));

    render(<SettingsPage />);

    await openAiRoutingDrawer();
    const aiSection = screen.getByRole('dialog', { name: '任务路由编辑' });
    const combos = within(aiSection).getAllByRole('combobox');
    const primaryGateway = combos[0] as HTMLSelectElement;
    const backupGateway = combos[1] as HTMLSelectElement;
    fireEvent.change(primaryGateway, { target: { value: 'aihubmix' } });
    fireEvent.change(backupGateway, { target: { value: 'gemini' } });

    fireEvent.click(within(aiSection).getAllByRole('button', { name: '显式模型 ID' })[1] as HTMLButtonElement);
    const customButtons = within(aiSection).getAllByRole('button', { name: '自定义 ID' });
    fireEvent.click(customButtons[0] as HTMLButtonElement);
    const backupCustomModelInput = within(aiSection).getByLabelText('自定义模型 ID') as HTMLInputElement;
    fireEvent.change(backupCustomModelInput, { target: { value: '' } });
    fireEvent.click(within(aiSection).getByRole('button', { name: '保存优先顺序' }));

    expect(saveExternalItems).not.toHaveBeenCalled();
    await waitFor(() => {
      expect(screen.getByText('备用路由配置缺失：需同时设置网关与模型，或全部清空。')).toBeInTheDocument();
    });
  });
});
