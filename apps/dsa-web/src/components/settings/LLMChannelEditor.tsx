import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type React from 'react';
import type { ParsedApiError } from '../../api/error';
import { getParsedApiError } from '../../api/error';
import { systemConfigApi } from '../../api/systemConfig';
import type { SystemConfigUpdateItem } from '../../types/systemConfig';
import { ApiErrorAlert, Badge, Button, Input, Select, SupportBanner, SupportPanel } from '../common';

type ChannelProtocol = 'openai' | 'deepseek' | 'gemini' | 'anthropic' | 'vertex_ai' | 'ollama';

interface ChannelPreset {
  label: string;
  protocol: ChannelProtocol;
  baseUrl: string;
  placeholder: string;
}

const CHANNEL_PRESETS: Record<string, ChannelPreset> = {
  aihubmix: {
    label: 'AIHubmix（聚合平台）',
    protocol: 'openai',
    baseUrl: 'https://aihubmix.com/v1',
    placeholder: 'gpt-4o-mini,claude-3-5-sonnet,qwen-plus',
  },
  deepseek: {
    label: 'DeepSeek 官方',
    protocol: 'deepseek',
    baseUrl: 'https://api.deepseek.com/v1',
    placeholder: 'deepseek-chat,deepseek-reasoner',
  },
  dashscope: {
    label: '通义千问（Dashscope）',
    protocol: 'openai',
    baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    placeholder: 'qwen-plus,qwen-turbo',
  },
  zhipu: {
    label: '智谱 GLM',
    protocol: 'openai',
    baseUrl: 'https://open.bigmodel.cn/api/paas/v4',
    placeholder: 'glm-4-flash,glm-4-plus',
  },
  moonshot: {
    label: 'Moonshot（月之暗面）',
    protocol: 'openai',
    baseUrl: 'https://api.moonshot.cn/v1',
    placeholder: 'moonshot-v1-8k',
  },
  siliconflow: {
    label: '硅基流动（SiliconFlow）',
    protocol: 'openai',
    baseUrl: 'https://api.siliconflow.cn/v1',
    placeholder: 'Qwen/Qwen3-8B,deepseek-ai/DeepSeek-V3',
  },
  openrouter: {
    label: 'OpenRouter',
    protocol: 'openai',
    baseUrl: 'https://openrouter.ai/api/v1',
    placeholder: 'openai/gpt-4o,anthropic/claude-3-5-sonnet',
  },
  gemini: {
    label: 'Gemini 官方',
    protocol: 'gemini',
    baseUrl: '',
    placeholder: 'gemini-2.5-flash,gemini-2.5-pro',
  },
  anthropic: {
    label: 'Anthropic 官方',
    protocol: 'anthropic',
    baseUrl: '',
    placeholder: 'claude-3-5-sonnet-20241022',
  },
  openai: {
    label: 'OpenAI 官方',
    protocol: 'openai',
    baseUrl: 'https://api.openai.com/v1',
    placeholder: 'gpt-4o,gpt-4o-mini',
  },
  ollama: {
    label: 'Ollama（本地）',
    protocol: 'ollama',
    baseUrl: 'http://127.0.0.1:11434',
    placeholder: 'llama3.2,qwen2.5',
  },
  custom: {
    label: '自定义渠道',
    protocol: 'openai',
    baseUrl: '',
    placeholder: 'model-name-1,model-name-2',
  },
};

const PROTOCOL_OPTIONS: Array<{ value: ChannelProtocol; label: string }> = [
  { value: 'openai', label: 'OpenAI Compatible' },
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'gemini', label: 'Gemini' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'vertex_ai', label: 'Vertex AI' },
  { value: 'ollama', label: 'Ollama' },
];

const MODEL_PLACEHOLDERS: Record<ChannelProtocol, string> = {
  openai: 'gpt-4o-mini,deepseek-chat,qwen-plus',
  deepseek: 'deepseek-chat,deepseek-reasoner',
  gemini: 'gemini-2.5-flash,gemini-2.5-pro',
  anthropic: 'claude-3-5-sonnet-20241022',
  vertex_ai: 'gemini-2.5-flash',
  ollama: 'llama3.2,qwen2.5',
};

const KNOWN_MODEL_PREFIXES = new Set([
  'openai',
  'anthropic',
  'gemini',
  'vertex_ai',
  'deepseek',
  'ollama',
  'cohere',
  'huggingface',
  'bedrock',
  'sagemaker',
  'azure',
  'replicate',
  'together_ai',
  'palm',
  'text-completion-openai',
  'command-r',
  'groq',
  'cerebras',
  'fireworks_ai',
  'friendliai',
]);

const FALSEY_VALUES = new Set(['0', 'false', 'no', 'off']);

interface ChannelConfig {
  name: string;
  protocol: ChannelProtocol;
  baseUrl: string;
  apiKey: string;
  models: string;
  enabled: boolean;
}

interface ChannelTestState {
  status: 'idle' | 'loading' | 'success' | 'error';
  text?: string;
}

interface RuntimeConfig {
  primaryModel: string;
  agentPrimaryModel: string;
  fallbackModels: string[];
  visionModel: string;
  temperature: string;
}

interface LLMChannelEditorProps {
  items: Array<{ key: string; value: string }>;
  onSaveItems: (
    updatedItems: SystemConfigUpdateItem[],
    successMessage: string
  ) => void | Promise<void>;
  adminUnlockToken?: string | null;
  disabled?: boolean;
  providerScopeName?: string;
  focusChannelName?: string;
  externalCreatePreset?: string | null;
  onExternalCreateHandled?: () => void;
}

interface ChannelRowProps {
  channel: ChannelConfig;
  index: number;
  busy: boolean;
  visibleKey: boolean;
  expanded: boolean;
  testState?: ChannelTestState;
  onUpdate: (index: number, field: keyof ChannelConfig, value: string | boolean) => void;
  onRemove: (index: number) => void;
  onToggleExpand: (index: number) => void;
  onToggleKeyVisibility: (index: number, nextVisible: boolean) => void;
  onTest: (channel: ChannelConfig, index: number) => void;
}

const ChannelRow: React.FC<ChannelRowProps> = ({
  channel,
  index,
  busy,
  visibleKey,
  expanded,
  testState,
  onUpdate,
  onRemove,
  onToggleExpand,
  onToggleKeyVisibility,
  onTest,
}) => {
  const preset = CHANNEL_PRESETS[channel.name];
  const displayName = preset?.label || channel.name;
  const modelCount = splitModels(channel.models).length;
  const hasKey = channel.apiKey.length > 0;
  const statusVariant = testState?.status === 'success'
    ? 'success'
    : testState?.status === 'error'
      ? 'danger'
      : testState?.status === 'loading'
        ? 'warning'
        : 'default';

  return (
    <div className="mb-2 overflow-hidden rounded-xl border settings-border settings-surface shadow-soft-card transition-all hover:settings-surface-hover">
      <div
        className="flex cursor-pointer select-none items-center gap-2.5 px-4 py-3 transition-colors hover:settings-surface-hover"
        onClick={() => onToggleExpand(index)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onToggleExpand(index);
          }
        }}
        role="button"
        tabIndex={0}
      >
        <span className={`w-4 shrink-0 text-[11px] text-muted-text transition-transform ${expanded ? 'rotate-90' : ''}`}>▶</span>

        <input
          type="checkbox"
          checked={channel.enabled}
          disabled={busy}
          className="settings-input-checkbox h-4 w-4 shrink-0 rounded border-border/70 bg-base"
          onClick={(e) => e.stopPropagation()}
          onChange={(e) => onUpdate(index, 'enabled', e.target.checked)}
        />

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-semibold text-foreground">{displayName}</span>
            <Badge variant="info" className="hidden sm:inline-flex">
              {channel.protocol}
            </Badge>
          </div>
          <p className="mt-0.5 truncate text-[11px] text-secondary-text">
            {modelCount > 0 ? `${modelCount} 个模型已配置` : '未配置模型'}
          </p>
        </div>

        <span className="flex shrink-0 items-center gap-2">
          {testState?.status === 'success' ? <span className="h-2 w-2 rounded-full bg-[var(--accent-positive)]" title="连接正常" /> : null}
          {testState?.status === 'error' ? <span className="h-2 w-2 rounded-full bg-[var(--accent-danger)]" title="连接失败" /> : null}
          {testState?.status === 'loading' ? <span className="h-2 w-2 rounded-full bg-[var(--accent-warning)] animate-pulse" title="测试中" /> : null}
          {!hasKey && channel.protocol !== 'ollama' ? <Badge variant="warning">未填 Key</Badge> : null}
          {testState?.status !== 'idle' ? (
            <Badge variant={statusVariant}>
              {testState?.status === 'success' ? '连接正常' : testState?.status === 'error' ? '连接失败' : '测试中'}
            </Badge>
          ) : null}
        </span>

        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-8 shrink-0 px-2 text-xs text-muted-text hover:text-danger"
          disabled={busy}
          onClick={(e) => {
            e.stopPropagation();
            onRemove(index);
          }}
          title="删除渠道"
        >
          ✕
        </Button>
      </div>

      {expanded ? (
        <div className="settings-surface-overlay-soft space-y-4 px-4 py-4">
          <div className="grid gap-2 sm:grid-cols-2">
            <Input
              label="渠道名称"
              value={channel.name}
              disabled={busy}
              onChange={(e) => onUpdate(index, 'name', e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ''))}
              placeholder="primary"
            />
            <div className="space-y-2">
              <label className="block text-sm font-medium text-foreground">协议</label>
              <Select
                value={channel.protocol}
                onChange={(v) => onUpdate(index, 'protocol', normalizeProtocol(v))}
                options={PROTOCOL_OPTIONS}
                disabled={busy}
                placeholder="选择协议"
              />
            </div>
          </div>

          <Input
            label="Base URL"
            value={channel.baseUrl}
            disabled={busy}
            onChange={(e) => onUpdate(index, 'baseUrl', e.target.value)}
            placeholder={
              channel.protocol === 'gemini' || channel.protocol === 'anthropic'
                ? '官方接口可留空'
                : preset?.baseUrl || 'https://api.example.com/v1'
            }
          />

          <Input
            label="API Key"
            type="password"
            allowTogglePassword
            iconType="key"
            passwordVisible={visibleKey}
            onPasswordVisibleChange={(nextVisible) => onToggleKeyVisibility(index, nextVisible)}
            value={channel.apiKey}
            disabled={busy}
            onChange={(e) => onUpdate(index, 'apiKey', e.target.value)}
            placeholder={channel.protocol === 'ollama' ? '本地 Ollama 可留空' : '支持多个 Key 逗号分隔'}
          />

          <Input
            label="模型（逗号分隔）"
            value={channel.models}
            disabled={busy}
            onChange={(e) => onUpdate(index, 'models', e.target.value)}
            placeholder={preset?.placeholder || MODEL_PLACEHOLDERS[channel.protocol]}
          />

          <div className="flex flex-wrap items-center gap-2 border-t settings-border-soft pt-3">
            <Button
              type="button"
              variant="gradient"
              size="sm"
              className="settings-accent-badge-soft px-3 text-[11px] shadow-none"
              disabled={busy}
              onClick={() => onTest(channel, index)}
            >
              {testState?.status === 'loading' ? '测试中...' : '测试连接'}
            </Button>
            {testState?.text ? (
              <span className={`rounded-full border px-2.5 py-1 text-xs ${
                testState.status === 'success'
                  ? 'border-success/25 bg-success/10 text-success'
                  : testState.status === 'error'
                    ? 'border-danger/25 bg-danger/10 text-danger'
                    : 'border-warning/25 bg-warning/10 text-warning'
              }`}
              >
                {testState.text}
              </span>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
};

function normalizeProtocol(value: string): ChannelProtocol {
  const normalized = value.trim().toLowerCase().replace(/-/g, '_');
  if (normalized === 'vertex' || normalized === 'vertexai') {
    return 'vertex_ai';
  }
  if (normalized === 'claude') {
    return 'anthropic';
  }
  if (normalized === 'google') {
    return 'gemini';
  }
  if (normalized === 'deepseek') {
    return 'deepseek';
  }
  if (normalized === 'gemini') {
    return 'gemini';
  }
  if (normalized === 'anthropic') {
    return 'anthropic';
  }
  if (normalized === 'vertex_ai') {
    return 'vertex_ai';
  }
  if (normalized === 'ollama') {
    return 'ollama';
  }
  return 'openai';
}

function inferProtocol(protocol: string, baseUrl: string, models: string[]): ChannelProtocol {
  const explicit = normalizeProtocol(protocol);
  if (protocol.trim()) {
    return explicit;
  }

  const firstPrefixedModel = models.find((model) => model.includes('/'));
  if (firstPrefixedModel) {
    return normalizeProtocol(firstPrefixedModel.split('/', 1)[0]);
  }

  if (baseUrl.includes('127.0.0.1') || baseUrl.includes('localhost')) {
    return 'openai';
  }

  return 'openai';
}

function parseEnabled(value: string | undefined): boolean {
  if (!value) {
    return true;
  }
  return !FALSEY_VALUES.has(value.trim().toLowerCase());
}

function splitModels(models: string): string[] {
  return models
    .split(',')
    .map((entry) => entry.trim())
    .filter(Boolean);
}

const PROTOCOL_ALIASES: Record<string, string> = {
  vertexai: 'vertex_ai',
  vertex: 'vertex_ai',
  claude: 'anthropic',
  google: 'gemini',
  openai_compatible: 'openai',
  openai_compat: 'openai',
};

function normalizeModelForRuntime(model: string, protocol: ChannelProtocol): string {
  const trimmedModel = model.trim();
  if (!trimmedModel) {
    return trimmedModel;
  }

  if (trimmedModel.includes('/')) {
    const rawPrefix = trimmedModel.split('/', 1)[0].trim();
    const lowerPrefix = rawPrefix.toLowerCase();
    const canonicalPrefix = PROTOCOL_ALIASES[lowerPrefix] || lowerPrefix;
    if (KNOWN_MODEL_PREFIXES.has(lowerPrefix) || KNOWN_MODEL_PREFIXES.has(canonicalPrefix)) {
      if (canonicalPrefix !== lowerPrefix && KNOWN_MODEL_PREFIXES.has(canonicalPrefix)) {
        return `${canonicalPrefix}/${trimmedModel.split('/').slice(1).join('/')}`;
      }
      return trimmedModel;
    }
    return `${protocol}/${trimmedModel}`;
  }

  return `${protocol}/${trimmedModel}`;
}

function resolveModelPreview(models: string, protocol: ChannelProtocol): string[] {
  return splitModels(models).map((model) => normalizeModelForRuntime(model, protocol));
}

function buildModelOptions(models: string[], selectedModel: string, autoLabel: string): Array<{ value: string; label: string }> {
  const options: Array<{ value: string; label: string }> = [{ value: '', label: autoLabel }];
  if (selectedModel && !models.includes(selectedModel)) {
    options.push({ value: selectedModel, label: `${selectedModel}（当前配置）` });
  }
  for (const model of models) {
    options.push({ value: model, label: model });
  }
  return options;
}

const MANAGED_PROVIDERS = new Set(['gemini', 'vertex_ai', 'anthropic', 'openai', 'deepseek']);

function usesDirectEnvProvider(model: string): boolean {
  if (!model || !model.includes('/')) return false;
  const provider = model.split('/', 1)[0].trim().toLowerCase();
  return Boolean(provider) && !MANAGED_PROVIDERS.has(provider);
}

function providerHasLegacyApiKey(provider: string, itemMap: Map<string, string>): boolean {
  const normalized = provider.trim().toLowerCase();
  if (!normalized) return false;
  const hasAny = (keys: string[]): boolean => keys.some((key) => Boolean((itemMap.get(key) || '').trim()));
  if (normalized === 'gemini' || normalized === 'vertex_ai') {
    return hasAny(['GEMINI_API_KEYS', 'GEMINI_API_KEY']);
  }
  if (normalized === 'anthropic') {
    return hasAny(['ANTHROPIC_API_KEYS', 'ANTHROPIC_API_KEY']);
  }
  if (normalized === 'deepseek') {
    return hasAny(['DEEPSEEK_API_KEYS', 'DEEPSEEK_API_KEY']);
  }
  if (normalized === 'openai') {
    return hasAny(['OPENAI_API_KEYS', 'OPENAI_API_KEY', 'AIHUBMIX_KEY', 'AIHUBMIX_KEYS']);
  }
  return false;
}

function hasRuntimeSourceForModel(model: string, availableModels: string[], itemMap: Map<string, string>): boolean {
  const normalized = (model || '').trim();
  if (!normalized) return true;
  if (availableModels.includes(normalized)) return true;
  if (usesDirectEnvProvider(normalized)) return true;
  const provider = normalized.includes('/') ? normalized.split('/', 1)[0].trim().toLowerCase() : 'openai';
  return providerHasLegacyApiKey(provider, itemMap);
}

function resolveTemperatureFromItems(itemMap: Map<string, string>): string {
  const unified = itemMap.get('LLM_TEMPERATURE');
  if (unified) return unified;

  const primaryModel = itemMap.get('LITELLM_MODEL') || '';
  const provider = primaryModel.includes('/') ? primaryModel.split('/')[0] : (primaryModel ? 'openai' : '');
  const providerTemperatureEnv: Record<string, string> = {
    gemini: 'GEMINI_TEMPERATURE',
    vertex_ai: 'GEMINI_TEMPERATURE',
    anthropic: 'ANTHROPIC_TEMPERATURE',
    openai: 'OPENAI_TEMPERATURE',
    deepseek: 'OPENAI_TEMPERATURE',
  };
  const preferredEnv = providerTemperatureEnv[provider];
  if (preferredEnv) {
    const val = itemMap.get(preferredEnv);
    if (val) return val;
  }

  for (const envName of ['GEMINI_TEMPERATURE', 'ANTHROPIC_TEMPERATURE', 'OPENAI_TEMPERATURE']) {
    const val = itemMap.get(envName);
    if (val) return val;
  }

  return '0.7';
}

function normalizeAgentPrimaryModel(model: string): string {
  const trimmedModel = model.trim();
  if (!trimmedModel) {
    return '';
  }
  if (trimmedModel.includes('/')) {
    return trimmedModel;
  }
  return `openai/${trimmedModel}`;
}

function parseRuntimeConfigFromItems(items: Array<{ key: string; value: string }>): RuntimeConfig {
  const itemMap = new Map(items.map((item) => [item.key, item.value]));
  return {
    primaryModel: itemMap.get('LITELLM_MODEL') || '',
    agentPrimaryModel: normalizeAgentPrimaryModel(itemMap.get('AGENT_LITELLM_MODEL') || ''),
    fallbackModels: splitModels(itemMap.get('LITELLM_FALLBACK_MODELS') || ''),
    visionModel: itemMap.get('VISION_MODEL') || '',
    temperature: resolveTemperatureFromItems(itemMap),
  };
}

function parseChannelsFromItems(items: Array<{ key: string; value: string }>): ChannelConfig[] {
  const itemMap = new Map(items.map((item) => [item.key, item.value]));
  const channelNames = (itemMap.get('LLM_CHANNELS') || '')
    .split(',')
    .map((segment) => segment.trim())
    .filter(Boolean);

  return channelNames.map((name) => {
    const upperName = name.toUpperCase();
    const baseUrl = itemMap.get(`LLM_${upperName}_BASE_URL`) || '';
    const rawModels = itemMap.get(`LLM_${upperName}_MODELS`) || '';
    const models = splitModels(rawModels);

    return {
      name: name.toLowerCase(),
      protocol: inferProtocol(itemMap.get(`LLM_${upperName}_PROTOCOL`) || '', baseUrl, models),
      baseUrl,
      apiKey: itemMap.get(`LLM_${upperName}_API_KEYS`) || itemMap.get(`LLM_${upperName}_API_KEY`) || '',
      models: rawModels,
      enabled: parseEnabled(itemMap.get(`LLM_${upperName}_ENABLED`)),
    };
  });
}

function channelsToUpdateItems(
  channels: ChannelConfig[],
  previousChannelNames: string[],
  runtimeConfig: RuntimeConfig,
  includeRuntimeConfig: boolean,
): Array<{ key: string; value: string }> {
  const updates: Array<{ key: string; value: string }> = [];
  const activeNames = channels.map((channel) => channel.name.toUpperCase());

  updates.push({ key: 'LLM_CHANNELS', value: channels.map((channel) => channel.name).join(',') });
  if (includeRuntimeConfig) {
    updates.push({ key: 'LITELLM_MODEL', value: runtimeConfig.primaryModel });
    updates.push({ key: 'AGENT_LITELLM_MODEL', value: runtimeConfig.agentPrimaryModel });
    updates.push({ key: 'LITELLM_FALLBACK_MODELS', value: runtimeConfig.fallbackModels.join(',') });
    updates.push({ key: 'VISION_MODEL', value: runtimeConfig.visionModel });
    updates.push({ key: 'LLM_TEMPERATURE', value: runtimeConfig.temperature });
  }

  for (const channel of channels) {
    const prefix = `LLM_${channel.name.toUpperCase()}`;
    const isMultiKey = channel.apiKey.includes(',');
    updates.push({ key: `${prefix}_PROTOCOL`, value: channel.protocol });
    updates.push({ key: `${prefix}_BASE_URL`, value: channel.baseUrl });
    updates.push({ key: `${prefix}_ENABLED`, value: channel.enabled ? 'true' : 'false' });
    updates.push({ key: `${prefix}_API_KEY${isMultiKey ? 'S' : ''}`, value: channel.apiKey });
    updates.push({ key: `${prefix}_API_KEY${isMultiKey ? '' : 'S'}`, value: '' });
    updates.push({ key: `${prefix}_MODELS`, value: channel.models });
  }

  for (const oldName of previousChannelNames) {
    const upperName = oldName.toUpperCase();
    if (activeNames.includes(upperName)) {
      continue;
    }

    const prefix = `LLM_${upperName}`;
    updates.push({ key: `${prefix}_PROTOCOL`, value: '' });
    updates.push({ key: `${prefix}_BASE_URL`, value: '' });
    updates.push({ key: `${prefix}_ENABLED`, value: '' });
    updates.push({ key: `${prefix}_API_KEY`, value: '' });
    updates.push({ key: `${prefix}_API_KEYS`, value: '' });
    updates.push({ key: `${prefix}_MODELS`, value: '' });
    updates.push({ key: `${prefix}_EXTRA_HEADERS`, value: '' });
  }

  return updates;
}

function channelsAreEqual(left: ChannelConfig, right: ChannelConfig): boolean {
  return (
    left.name === right.name
    && left.protocol === right.protocol
    && left.baseUrl === right.baseUrl
    && left.apiKey === right.apiKey
    && left.models === right.models
    && left.enabled === right.enabled
  );
}

function normalizeProviderScopeName(value?: string): string {
  return String(value || '').trim().toLowerCase();
}

function resolveChannelScopeName(channelName: string): string {
  const normalizedName = normalizeProviderScopeName(channelName);
  if (!normalizedName) {
    return '';
  }
  const baseName = normalizedName.replace(/\d+$/, '');
  return CHANNEL_PRESETS[baseName] ? baseName : normalizedName;
}

export const LLMChannelEditor: React.FC<LLMChannelEditorProps> = ({
  items,
  onSaveItems,
  adminUnlockToken,
  disabled = false,
  providerScopeName = '',
  focusChannelName = '',
  externalCreatePreset = null,
  onExternalCreateHandled,
}) => {
  const normalizedScopeName = normalizeProviderScopeName(providerScopeName);
  const scopedPreset = normalizedScopeName ? CHANNEL_PRESETS[normalizedScopeName] : null;
  const providerScopedMode = Boolean(normalizedScopeName && scopedPreset);
  const rawItemMap = useMemo(() => new Map(items.map((item) => [item.key, item.value])), [items]);
  const initialChannels = useMemo(() => parseChannelsFromItems(items), [items]);
  const initialNames = useMemo(() => initialChannels.map((channel) => channel.name), [initialChannels]);
  const initialRuntimeConfig = useMemo(() => parseRuntimeConfigFromItems(items), [items]);
  const hasLitellmConfig = useMemo(
    () => items.some((item) => item.key === 'LITELLM_CONFIG' && item.value.trim().length > 0),
    [items],
  );
  const managesRuntimeConfig = !hasLitellmConfig;

  const channelsFingerprint = useMemo(() => JSON.stringify(initialChannels), [initialChannels]);
  const runtimeFingerprint = useMemo(() => JSON.stringify(initialRuntimeConfig), [initialRuntimeConfig]);

  const [channels, setChannels] = useState<ChannelConfig[]>(initialChannels);
  const [runtimeConfig, setRuntimeConfig] = useState<RuntimeConfig>(initialRuntimeConfig);
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<
    | { type: 'success'; text: string }
    | { type: 'error'; error: ParsedApiError }
    | { type: 'local-error'; text: string }
    | null
  >(null);
  const [visibleKeys, setVisibleKeys] = useState<Record<number, boolean>>({});
  const [testStates, setTestStates] = useState<Record<number, ChannelTestState>>({});
  const [expandedRows, setExpandedRows] = useState<Record<number, boolean>>({});
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [addPreset, setAddPreset] = useState(normalizedScopeName || 'aihubmix');

  const prevChannelsRef = useRef(channelsFingerprint);
  const prevRuntimeRef = useRef(runtimeFingerprint);
  const channelRowRefs = useRef<Record<number, HTMLDivElement | null>>({});

  useEffect(() => {
    if (prevChannelsRef.current === channelsFingerprint && prevRuntimeRef.current === runtimeFingerprint) {
      return;
    }
    prevChannelsRef.current = channelsFingerprint;
    prevRuntimeRef.current = runtimeFingerprint;
    setChannels(initialChannels);
    setRuntimeConfig(initialRuntimeConfig);
    setVisibleKeys({});
    setTestStates({});
    setExpandedRows({});
    setSaveMessage(null);
    setIsCollapsed(false);
  }, [channelsFingerprint, runtimeFingerprint, initialChannels, initialRuntimeConfig]);

  useEffect(() => {
    if (!providerScopedMode) {
      return;
    }
    setAddPreset(normalizedScopeName);
  }, [normalizedScopeName, providerScopedMode]);

  const availableModels = useMemo(() => {
    if (!managesRuntimeConfig) {
      return [];
    }
    const seen = new Set<string>();
    const models: string[] = [];
    for (const channel of channels) {
      if (!channel.enabled || !channel.name.trim()) {
        continue;
      }
      for (const model of resolveModelPreview(channel.models, channel.protocol)) {
        if (!model || seen.has(model)) {
          continue;
        }
        seen.add(model);
        models.push(model);
      }
    }
    return models;
  }, [channels, managesRuntimeConfig]);

  const hasChanges = useMemo(() => {
    const runtimeChanged = (
      runtimeConfig.primaryModel !== initialRuntimeConfig.primaryModel
      || runtimeConfig.agentPrimaryModel !== initialRuntimeConfig.agentPrimaryModel
      || runtimeConfig.visionModel !== initialRuntimeConfig.visionModel
      || runtimeConfig.temperature !== initialRuntimeConfig.temperature
      || runtimeConfig.fallbackModels.join(',') !== initialRuntimeConfig.fallbackModels.join(',')
    );

    if (runtimeChanged || channels.length !== initialChannels.length) {
      return true;
    }
    return channels.some((channel, index) => !channelsAreEqual(channel, initialChannels[index]));
  }, [channels, initialChannels, initialRuntimeConfig, runtimeConfig]);

  const visibleChannelEntries = useMemo(() => {
    return channels
      .map((channel, index) => ({ channel, index }))
      .filter((entry) => {
        if (!providerScopedMode) {
          return true;
        }
        return resolveChannelScopeName(entry.channel.name) === normalizedScopeName;
      });
  }, [channels, normalizedScopeName, providerScopedMode]);

  const busy = disabled || isSaving;

  const updateChannel = (index: number, field: keyof ChannelConfig, value: string | boolean) => {
    setChannels((previous) => previous.map((channel, rowIndex) => {
      if (rowIndex !== index) return channel;
      const updated = { ...channel, [field]: value };

      if (field === 'name' && typeof value === 'string') {
        const newPreset = CHANNEL_PRESETS[value];
        if (newPreset) {
          const oldPreset = CHANNEL_PRESETS[channel.name];
          if (!updated.baseUrl || updated.baseUrl === (oldPreset?.baseUrl ?? '')) {
            updated.baseUrl = newPreset.baseUrl;
          }
          updated.protocol = newPreset.protocol;
          if (!updated.models || updated.models === (oldPreset?.placeholder ?? '')) {
            updated.models = newPreset.placeholder;
          }
        }
      }

      return updated;
    }));
    setTestStates((previous) => {
      if (!(index in previous)) {
        return previous;
      }
      const next = { ...previous };
      delete next[index];
      return next;
    });
  };

  const removeChannel = (index: number) => {
    setChannels((previous) => previous.filter((_, rowIndex) => rowIndex !== index));
    setVisibleKeys({});
    setTestStates({});
    setExpandedRows({});
  };

  const addChannel = useCallback((presetKey?: string) => {
    const nextPresetKey = presetKey || addPreset;
    const preset = CHANNEL_PRESETS[nextPresetKey] || CHANNEL_PRESETS.custom;
    const baseName = nextPresetKey === 'custom' ? 'custom' : nextPresetKey;
    let nextIndex = 0;
    setChannels((previous) => {
      const existingNames = new Set(previous.map((channel) => channel.name));
      let nextName = baseName;
      let counter = 2;
      while (existingNames.has(nextName)) {
        nextName = `${baseName}${counter}`;
        counter += 1;
      }
      nextIndex = previous.length;

      return [
        ...previous,
        {
          name: nextName,
          protocol: preset.protocol,
          baseUrl: preset.baseUrl,
          apiKey: '',
          models: preset.placeholder || '',
          enabled: true,
        },
      ];
    });
    setTestStates({});
    setExpandedRows((prev) => ({ ...prev, [nextIndex]: true }));
    setIsCollapsed(false);
    window.setTimeout(() => {
      channelRowRefs.current[nextIndex]?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 0);
  }, [addPreset]);
  useEffect(() => {
    const requestedPreset = String(externalCreatePreset || '').trim().toLowerCase();
    if (!requestedPreset) return;
    setAddPreset(requestedPreset);
    addChannel(requestedPreset);
    onExternalCreateHandled?.();
  }, [addChannel, externalCreatePreset, onExternalCreateHandled]);
  useEffect(() => {
    const targetName = String(focusChannelName || '').trim().toLowerCase();
    if (!targetName) return;
    const targetIndex = channels.findIndex((channel) => channel.name.trim().toLowerCase() === targetName);
    if (targetIndex < 0) return;
    setIsCollapsed(false);
    setExpandedRows((prev) => ({ ...prev, [targetIndex]: true }));
    window.setTimeout(() => {
      channelRowRefs.current[targetIndex]?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 0);
  }, [channels, focusChannelName]);

  const handleSave = async () => {
    const hasEmptyName = channels.some((channel) => !channel.name.trim());
    if (hasEmptyName) {
      setSaveMessage({ type: 'local-error', text: '渠道名称不能为空，且只能包含字母、数字或下划线。' });
      return;
    }

    if (managesRuntimeConfig && availableModels.length > 0) {
      const invalidPrimaryModel = runtimeConfig.primaryModel
        && !hasRuntimeSourceForModel(runtimeConfig.primaryModel, availableModels, rawItemMap);
      if (invalidPrimaryModel) {
        setSaveMessage({ type: 'local-error', text: '当前主模型不在已启用渠道的模型列表中，请重新选择。' });
        return;
      }

      const invalidAgentPrimaryModel = runtimeConfig.agentPrimaryModel
        && !hasRuntimeSourceForModel(runtimeConfig.agentPrimaryModel, availableModels, rawItemMap);
      if (invalidAgentPrimaryModel) {
        setSaveMessage({ type: 'local-error', text: '当前 Agent 主模型不在已启用渠道的模型列表中，请重新选择。' });
        return;
      }

      const invalidFallbackModel = runtimeConfig.fallbackModels.some(
        (model) => !hasRuntimeSourceForModel(model, availableModels, rawItemMap),
      );
      if (invalidFallbackModel) {
        setSaveMessage({
          type: 'local-error',
          text: 'Fallback 仅支持当前运行时可访问模型（已启用渠道声明或可用直连 Provider Key）。跨 Provider 失败切换请在任务层备用路由中配置。',
        });
        return;
      }

      const invalidVisionModel = runtimeConfig.visionModel
        && !hasRuntimeSourceForModel(runtimeConfig.visionModel, availableModels, rawItemMap);
      if (invalidVisionModel) {
        setSaveMessage({ type: 'local-error', text: '当前 Vision 模型不在已启用渠道的模型列表中，请重新选择。' });
        return;
      }
    }

    setIsSaving(true);
    setSaveMessage(null);

    try {
      const updateItems = channelsToUpdateItems(channels, initialNames, runtimeConfig, managesRuntimeConfig);
      const successMessage = managesRuntimeConfig ? 'AI 配置已保存' : '渠道配置已保存';
      await onSaveItems(updateItems, successMessage);
      setSaveMessage({ type: 'success', text: successMessage });
    } catch (error: unknown) {
      setSaveMessage({ type: 'error', error: getParsedApiError(error) });
    } finally {
      setIsSaving(false);
    }
  };

  const handleTest = async (channel: ChannelConfig, index: number) => {
    setTestStates((previous) => ({
      ...previous,
      [index]: { status: 'loading', text: '测试中...' },
    }));

    try {
      const result = await systemConfigApi.testLLMChannel({
        name: channel.name,
        protocol: channel.protocol,
        baseUrl: channel.baseUrl,
        apiKey: channel.apiKey,
        models: splitModels(channel.models),
        enabled: channel.enabled,
      }, { adminUnlockToken });

      const text = result.success
        ? `连接成功${result.resolvedModel ? ` · ${result.resolvedModel}` : ''}${result.latencyMs ? ` · ${result.latencyMs} ms` : ''}`
        : (result.error || result.message || '测试失败');

      setTestStates((previous) => ({
        ...previous,
        [index]: {
          status: result.success ? 'success' : 'error',
          text,
        },
      }));
    } catch (error: unknown) {
      const parsed = getParsedApiError(error);
      setTestStates((previous) => ({
        ...previous,
        [index]: { status: 'error', text: parsed.message || '测试失败' },
      }));
    }
  };

  const toggleKeyVisibility = (index: number, nextVisible: boolean) => {
    setVisibleKeys((previous) => ({ ...previous, [index]: nextVisible }));
  };

  const toggleExpand = (index: number) => {
    setExpandedRows((previous) => ({ ...previous, [index]: !previous[index] }));
  };

  const setPrimaryModel = (value: string) => {
    setRuntimeConfig((previous) => ({
      ...previous,
      primaryModel: value,
      fallbackModels: previous.fallbackModels.filter((model) => model !== value),
    }));
  };

  const toggleFallbackModel = (model: string) => {
    setRuntimeConfig((previous) => {
      const alreadySelected = previous.fallbackModels.includes(model);
      return {
        ...previous,
        fallbackModels: alreadySelected
          ? previous.fallbackModels.filter((item) => item !== model)
          : [...previous.fallbackModels, model],
      };
    });
  };

  return (
    <div className="space-y-4">
      <button
        type="button"
        className="flex w-full items-center justify-between rounded-[1.35rem] border settings-border settings-surface px-5 py-4 text-left shadow-soft-card transition-all duration-200 hover:settings-surface-hover"
        onClick={() => setIsCollapsed((previous) => !previous)}
      >
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <h3 className="text-base font-semibold text-foreground">
              {providerScopedMode && scopedPreset ? `${scopedPreset.label} 高级配置` : 'AI 模型配置'}
            </h3>
            <Badge variant="info" className="settings-accent-badge">渠道管理</Badge>
          </div>
          <p className="text-xs text-muted-text">
            {providerScopedMode && scopedPreset
              ? `只管理 ${scopedPreset.label} 的高级渠道。配置会自动同步到 .env 文件。`
              : '添加服务商渠道，填入 API Key 和模型名称即可。配置会自动同步到 .env 文件。'}
          </p>
        </div>
        <span className="text-xs text-muted-text">{isCollapsed ? '▶ 展开' : '▼ 收起'}</span>
      </button>

      {!isCollapsed ? (
        <div className="space-y-4 animate-in fade-in slide-in-from-top-2 duration-300">
          <div className="settings-surface rounded-[1.35rem] border settings-border p-4 shadow-soft-card">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <h4 className="text-sm font-medium text-foreground">
                  {providerScopedMode ? '新增当前 Provider 渠道' : '快速添加渠道'}
                </h4>
                <p className="mt-1 text-xs text-secondary-text">
                  {providerScopedMode && scopedPreset
                    ? `只创建 ${scopedPreset.label} 渠道草稿。`
                    : '先选择预设服务商，再一键创建配置草稿。'}
                </p>
              </div>
              <Badge variant="default" className="settings-border settings-surface-hover text-muted-text">
                {visibleChannelEntries.length} 个渠道
              </Badge>
            </div>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="gradient"
                className="whitespace-nowrap"
                disabled={busy}
                onClick={() => addChannel(providerScopedMode ? normalizedScopeName : undefined)}
              >
                + 添加渠道
              </Button>
              {providerScopedMode && scopedPreset ? (
                <div className="flex-1 rounded-xl border border-border/50 bg-base/40 px-3 py-2 text-sm font-medium text-secondary-text">
                  {scopedPreset.label}
                </div>
              ) : (
                <Select
                  value={addPreset}
                  onChange={setAddPreset}
                  options={Object.entries(CHANNEL_PRESETS).map(([value, preset]) => ({
                    value,
                    label: preset.label,
                  }))}
                  disabled={busy}
                  placeholder="选择服务商"
                  className="flex-1"
                />
              )}
            </div>
            {!providerScopedMode ? (
              <SupportPanel
                className="mt-3 rounded-xl border settings-border-soft settings-surface-overlay-soft px-3 py-2"
                body="渠道条目负责管理服务商连接信息；真正生效的主模型、Fallback、Vision 与 Temperature 会在下方统一保存。"
                bodyClassName="text-muted-text"
              />
            ) : null}
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between px-1">
              <span className="text-xs font-medium uppercase tracking-wider text-muted-text">渠道列表</span>
              {visibleChannelEntries.length > 0 ? (
                <span className="text-[10px] text-muted-text">
                  {visibleChannelEntries.filter((entry) => entry.channel.enabled).length}/{visibleChannelEntries.length} 已启用
                </span>
              ) : null}
            </div>

            {visibleChannelEntries.length === 0 ? (
              <div className="settings-surface-overlay-muted rounded-[1.35rem] border border-dashed border-border/28 px-4 py-10 text-center">
                <p className="text-sm font-medium text-foreground">
                  {providerScopedMode && scopedPreset ? `还没有 ${scopedPreset.label} 渠道` : '还没有渠道'}
                </p>
                <p className="mt-1 text-xs leading-5 text-muted-text">
                  {providerScopedMode
                    ? '点击“添加渠道”即可为当前 Provider 创建高级渠道。'
                    : '选择服务商预设后点击“添加渠道”即可开始配置。'}
                </p>
              </div>
            ) : visibleChannelEntries.map(({ channel, index }) => (
              <div
                key={index}
                ref={(node) => {
                  channelRowRefs.current[index] = node;
                }}
              >
                <ChannelRow
                  channel={channel}
                  index={index}
                  busy={busy}
                  visibleKey={Boolean(visibleKeys[index])}
                  expanded={Boolean(expandedRows[index])}
                  testState={testStates[index]}
                  onUpdate={updateChannel}
                  onRemove={removeChannel}
                  onToggleExpand={toggleExpand}
                  onToggleKeyVisibility={toggleKeyVisibility}
                  onTest={(ch, idx) => void handleTest(ch, idx)}
                />
              </div>
            ))}
          </div>

          {!providerScopedMode && managesRuntimeConfig ? (
            <div className="settings-surface rounded-[1.35rem] border settings-border p-4 shadow-soft-card">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <span className="settings-accent-text text-xs font-medium uppercase tracking-wider">运行时参数</span>
                  <p className="mt-1 text-[11px] text-muted-text">主模型、Fallback、Vision 与 Temperature 会直接写入运行时配置。</p>
                </div>
                <Badge variant="default" className="settings-border settings-surface-hover text-muted-text">Runtime</Badge>
              </div>
              <div className="mb-4">
                <label className="mb-1 block text-xs text-muted-text">Temperature</label>
                <div className="flex items-center gap-3">
                  <input
                    type="range"
                    min="0"
                    max="2"
                    step="0.1"
                    value={runtimeConfig.temperature}
                    disabled={busy}
                    onChange={(event) => setRuntimeConfig((previous) => ({ ...previous, temperature: event.target.value }))}
                    className="settings-input-checkbox h-1.5 flex-1 cursor-pointer rounded-full bg-border/60"
                  />
                  <span className="w-8 text-right text-sm text-secondary-text">{runtimeConfig.temperature}</span>
                </div>
                <p className="mt-1 text-[11px] text-secondary-text">
                  控制模型输出随机性，0 为确定性输出，2 为最大随机性，推荐 0.7。
                </p>
              </div>

              {availableModels.length === 0 ? (
                <SupportPanel
                  className="rounded-xl border border-dashed settings-border-soft settings-surface-overlay-soft px-3 py-3"
                  title="还没有可用模型"
                  body="先添加至少一个已启用渠道并填写模型，下面的主模型、Fallback 和 Vision 选项才会出现。"
                />
              ) : (
                <div className="space-y-4">
                  <div>
                    <label className="mb-1 block text-xs text-muted-text">主模型</label>
                    <Select
                      value={runtimeConfig.primaryModel}
                      onChange={setPrimaryModel}
                      options={buildModelOptions(availableModels, runtimeConfig.primaryModel, '自动（使用第一个可用模型）')}
                      disabled={busy}
                      placeholder=""
                    />
                  </div>

                  <div>
                    <label className="mb-1 block text-xs text-muted-text">Agent 主模型</label>
                    <Select
                      value={runtimeConfig.agentPrimaryModel}
                      onChange={(value) => setRuntimeConfig((previous) => ({
                        ...previous,
                        agentPrimaryModel: normalizeAgentPrimaryModel(value),
                      }))}
                      options={buildModelOptions(availableModels, runtimeConfig.agentPrimaryModel, '自动（继承普通分析主模型）')}
                      disabled={busy}
                      placeholder=""
                    />
                  </div>

                  <div>
                    <label className="mb-2 block text-xs text-muted-text">Fallback 模型</label>
                    <div className="space-y-2 rounded-xl border border-border/30 bg-background/10 p-3">
                      {availableModels.map((model) => (
                        <label key={model} className="flex items-center gap-2 text-sm text-secondary-text">
                          <input
                            type="checkbox"
                            checked={runtimeConfig.fallbackModels.includes(model)}
                            disabled={busy || model === runtimeConfig.primaryModel}
                            onChange={() => toggleFallbackModel(model)}
                            className="settings-input-checkbox h-4 w-4 rounded border-border/70 bg-base"
                          />
                          <span>{model}</span>
                        </label>
                      ))}
                    </div>
                    <p className="mt-1 text-[11px] text-secondary-text">
                      Fallback 只会在主模型失败时使用，且仅接受当前运行时可访问模型（渠道声明或可用直连 Provider Key）。
                      跨 Provider 的任务级容灾请在上层任务路由的“备用路由”配置。
                    </p>
                  </div>

                  <div>
                    <label className="mb-1 block text-xs text-muted-text">Vision 模型</label>
                    <Select
                      value={runtimeConfig.visionModel}
                      onChange={(value) => setRuntimeConfig((previous) => ({ ...previous, visionModel: value }))}
                      options={buildModelOptions(availableModels, runtimeConfig.visionModel, '自动（跟随 Vision 默认逻辑）')}
                      disabled={busy}
                      placeholder=""
                    />
                  </div>
                </div>
              )}
            </div>
          ) : providerScopedMode ? null : (
            <SupportBanner
              tone="warning"
              title="当前由 `LITELLM_CONFIG` 接管运行时选择"
              body="主模型、Fallback、Vision 与 Temperature 继续在下方通用字段中管理；这里仅保存渠道条目，不会覆盖 YAML 运行时选择。"
              className="rounded-[1.35rem] px-4"
            />
          )}

          <div className="flex flex-wrap items-center gap-3">
            <Button
              type="button"
              variant="settings-primary"
              glow
              disabled={busy || !hasChanges}
              onClick={() => void handleSave()}
            >
              {isSaving ? '保存中...' : providerScopedMode || !managesRuntimeConfig ? '保存渠道配置' : '保存 AI 配置'}
            </Button>
            {!hasChanges ? <span className="text-xs text-muted-text">当前没有未保存的改动</span> : null}
          </div>

          {saveMessage?.type === 'success' ? (
            <SupportBanner tone="success" title={saveMessage.text} role="status" className="py-2" />
          ) : null}

          {saveMessage?.type === 'local-error' ? (
            <SupportBanner tone="danger" title={saveMessage.text} role="alert" className="py-2" />
          ) : null}

          {saveMessage?.type === 'error' ? <ApiErrorAlert error={saveMessage.error} /> : null}
        </div>
      ) : null}
    </div>
  );
};
