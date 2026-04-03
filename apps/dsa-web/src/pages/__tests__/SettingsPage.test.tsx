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
  useAuthMock: vi.fn(),
  useSystemConfigMock: vi.fn(),
}));

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
  }: {
    onSaveItems: (items: Array<{ key: string; value: string }>, successMessage: string) => void;
  }) => (
    <button
      type="button"
      onClick={() => onSaveItems([{ key: 'LLM_CHANNELS', value: 'primary,backup' }], '渠道配置已保存')}
    >
      save llm channels
    </button>
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
  { category: 'agent', title: 'Agent', description: 'Agent 配置', displayOrder: 4, fields: [] },
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

describe('SettingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.sessionStorage.clear();
    window.sessionStorage.setItem('dsa-admin-settings-unlock-token', 'unit-test-token');
    window.sessionStorage.setItem('dsa-admin-settings-unlock-expires-at', String(Date.now() + 60_000));
    useAuthMock.mockReturnValue({
      authEnabled: true,
      passwordChangeable: true,
      setupState: 'enabled',
      refreshStatus,
    });
    useSystemConfigMock.mockReturnValue(buildSystemConfigState());
  });

  it('renders category navigation and auth settings modules', async () => {
    render(<SettingsPage />);

    expect(await screen.findByRole('heading', { name: '系统设置' })).toBeInTheDocument();
    expect(await screen.findByText('认证与登录保护')).toBeInTheDocument();
    expect(await screen.findByText('修改密码')).toBeInTheDocument();
    expect(load).toHaveBeenCalled();
  });

  it('keeps admin controls locked by default without unlock token', () => {
    window.sessionStorage.clear();
    useSystemConfigMock.mockReturnValue(buildSystemConfigState({
      activeCategory: 'system',
      isAdminUnlocked: false,
      adminUnlockToken: null,
      adminUnlockExpiresAt: null,
    }));

    render(<SettingsPage />);

    expect(screen.getByText('锁定状态下仅可浏览，无法修改系统级配置。')).toBeInTheDocument();
    expect(screen.queryByText('认证与登录保护')).not.toBeInTheDocument();
    expect(screen.queryByText('修改密码')).not.toBeInTheDocument();
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

    const aiSection = screen.getByRole('heading', { name: '当前生效 AI 配置' }).closest('section');
    expect(aiSection).not.toBeNull();
    const combos = within(aiSection as HTMLElement).getAllByRole('combobox');

    const primaryGateway = combos[0] as HTMLSelectElement;
    const backupGateway = combos[2] as HTMLSelectElement;

    expect(primaryGateway).not.toBeDisabled();
    expect(primaryGateway.querySelector('option[value="aihubmix"]')).not.toBeNull();
    expect(backupGateway).toBeDisabled();
    expect(screen.getByText('备用路由需要至少两个已配置 AI Provider。')).toBeInTheDocument();
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

    const aiSection = screen.getByRole('heading', { name: '当前生效 AI 配置' }).closest('section');
    expect(aiSection).not.toBeNull();
    const combos = within(aiSection as HTMLElement).getAllByRole('combobox');

    const primaryGateway = combos[0] as HTMLSelectElement;
    const backupGateway = combos[2] as HTMLSelectElement;

    expect(primaryGateway).not.toBeDisabled();
    expect(backupGateway).not.toBeDisabled();
    expect(primaryGateway.querySelector('option[value="aihubmix"]')).not.toBeNull();
    expect(primaryGateway.querySelector('option[value="gemini"]')).not.toBeNull();
    expect(backupGateway.querySelector('option[value="aihubmix"]')).not.toBeNull();
    expect(backupGateway.querySelector('option[value="gemini"]')).not.toBeNull();
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

    const aiSection = screen.getByRole('heading', { name: '当前生效 AI 配置' }).closest('section');
    expect(aiSection).not.toBeNull();
    const combos = within(aiSection as HTMLElement).getAllByRole('combobox');

    const primaryGateway = combos[0] as HTMLSelectElement;
    const backupGateway = combos[2] as HTMLSelectElement;

    expect(primaryGateway).toBeDisabled();
    expect(backupGateway).toBeDisabled();
    expect(screen.getByText(/至少一个 AI Provider 凭据/)).toBeInTheDocument();
    expect(screen.getByText('备用路由需要至少两个已配置 AI Provider。')).toBeInTheDocument();
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

    const aiSection = screen.getByRole('heading', { name: '当前生效 AI 配置' }).closest('section');
    expect(aiSection).not.toBeNull();
    const combos = within(aiSection as HTMLElement).getAllByRole('combobox');
    const primaryGateway = combos[0] as HTMLSelectElement;
    const primaryModel = combos[1] as HTMLSelectElement;

    fireEvent.change(primaryGateway, { target: { value: 'gemini' } });
    fireEvent.change(primaryModel, { target: { value: 'gemini/gemini-2.5-flash' } });
    fireEvent.click(within(aiSection as HTMLElement).getByRole('button', { name: '保存优先顺序' }));

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

    const aiSection = screen.getByRole('heading', { name: '当前生效 AI 配置' }).closest('section');
    expect(aiSection).not.toBeNull();
    const combos = within(aiSection as HTMLElement).getAllByRole('combobox');

    fireEvent.change(combos[0] as HTMLSelectElement, { target: { value: 'gemini' } });
    const customButtons = within(aiSection as HTMLElement).getAllByRole('button', { name: '自定义 ID' });
    fireEvent.click(customButtons[0] as HTMLButtonElement);
    const primaryCustomModelInput = within(aiSection as HTMLElement).getByLabelText('自定义模型 ID') as HTMLInputElement;
    fireEvent.change(primaryCustomModelInput, { target: { value: '' } });
    fireEvent.click(within(aiSection as HTMLElement).getByRole('button', { name: '保存优先顺序' }));

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

    const aiSection = screen.getByRole('heading', { name: '当前生效 AI 配置' }).closest('section');
    expect(aiSection).not.toBeNull();
    const combos = within(aiSection as HTMLElement).getAllByRole('combobox');
    const primaryGateway = combos[0] as HTMLSelectElement;
    const primaryModel = combos[1] as HTMLSelectElement;
    const backupGateway = combos[2] as HTMLSelectElement;
    fireEvent.change(primaryGateway, { target: { value: 'aihubmix' } });
    fireEvent.change(primaryModel, { target: { value: 'openai/gpt-4.1-mini' } });
    fireEvent.change(backupGateway, { target: { value: 'gemini' } });

    const customButtons = within(aiSection as HTMLElement).getAllByRole('button', { name: '自定义 ID' });
    fireEvent.click(customButtons[1] as HTMLButtonElement);
    const backupCustomModelInput = within(aiSection as HTMLElement).getByLabelText('自定义模型 ID') as HTMLInputElement;
    fireEvent.change(backupCustomModelInput, { target: { value: '' } });
    fireEvent.click(within(aiSection as HTMLElement).getByRole('button', { name: '保存优先顺序' }));

    expect(saveExternalItems).not.toHaveBeenCalled();
    await waitFor(() => {
      expect(screen.getByText('备用路由配置不完整：请同时设置网关和模型，或同时清空。')).toBeInTheDocument();
    });
  });
});
