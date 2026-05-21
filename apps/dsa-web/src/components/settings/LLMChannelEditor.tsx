import { useEffect, useMemo, useRef, useState } from 'react';
import type React from 'react';
import type { ParsedApiError } from '../../api/error';
import { getParsedApiError } from '../../api/error';
import { systemConfigApi } from '../../api/systemConfig';
import type { LLMCapabilityCheck, LLMCapabilityCheckResult } from '../../types/systemConfig';
import { ApiErrorAlert, Badge, Button, InlineAlert, Input, Select, StatusDot, Tooltip } from '../common';
import type { ChannelProtocol } from './llmProviderTemplates';
import {
  LLM_PROVIDER_CAPABILITY_LABELS,
  LLM_PROVIDER_TEMPLATES,
  MODEL_PLACEHOLDERS_BY_PROTOCOL,
  getProviderTemplate,
  isKnownProviderTemplate,
} from './llmProviderTemplates';
import { SettingsHelpButton } from './SettingsHelpButton';

const PROTOCOL_OPTIONS: Array<{ value: ChannelProtocol; label: string }> = [
  { value: 'openai', label: 'OpenAI Compatible' },
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'gemini', label: 'Gemini' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'vertex_ai', label: 'Vertex AI' },
  { value: 'ollama', label: 'Ollama' },
];

const KNOWN_MODEL_PREFIXES = new Set([
  'openai',
  'anthropic',
  'gemini',
  'vertex_ai',
  'deepseek',
  'minimax',
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

const RUNTIME_CAPABILITY_OPTIONS: Array<{ value: LLMCapabilityCheck; label: string; hint: string }> = [
  { value: 'json', label: 'JSON', hint: 'response_format JSON 출력을 사용할 수 있는지 확인합니다.' },
  { value: 'tools', label: 'Tools', hint: 'function/tool calling 사용 가능 여부를 확인합니다.' },
  { value: 'stream', label: 'Stream', hint: '스트리밍 출력에서 유효한 chunk를 반환하는지 확인합니다.' },
  { value: 'vision', label: 'Vision', hint: '현재 모델이 image_url 입력을 받는지 확인합니다.' },
];

const CAPABILITY_STATUS_LABELS: Record<LLMCapabilityCheckResult['status'], string> = {
  passed: '통과',
  failed: '실패',
  skipped: '건너뜀',
};

interface ChannelConfig {
  id: string;
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
  hint?: string;
}

interface ChannelDiscoveryState {
  status: 'idle' | 'loading' | 'success' | 'error';
  text?: string;
  hint?: string;
  models: string[];
}

interface ChannelCapabilityState {
  selected: LLMCapabilityCheck[];
  status: 'idle' | 'loading' | 'success' | 'error';
  text?: string;
  hint?: string;
  results: Partial<Record<LLMCapabilityCheck, LLMCapabilityCheckResult>>;
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
  configVersion: string;
  maskToken: string;
  onSaved: (updatedItems: Array<{ key: string; value: string }>) => void | Promise<void>;
  disabled?: boolean;
}

interface ChannelRowProps {
  channel: ChannelConfig;
  index: number;
  busy: boolean;
  visibleKey: boolean;
  expanded: boolean;
  testState?: ChannelTestState;
  discoveryState?: ChannelDiscoveryState;
  capabilityState?: ChannelCapabilityState;
  onUpdate: (index: number, field: keyof ChannelConfig, value: string | boolean) => void;
  onRemove: (index: number) => void;
  onToggleExpand: (index: number) => void;
  onToggleKeyVisibility: (index: number, nextVisible: boolean) => void;
  onTest: (channel: ChannelConfig, index: number) => void;
  onDiscoverModels: (channel: ChannelConfig) => void;
  onToggleCapability: (channel: ChannelConfig, capability: LLMCapabilityCheck) => void;
  onCheckCapabilities: (channel: ChannelConfig) => void;
}

const LLM_CHANNEL_HELP_DOCS = [
  {
    label: 'LLM 설정 가이드',
    href: 'https://github.com/ZhuLinsen/daily_stock_analysis/blob/main/docs/LLM_CONFIG_GUIDE.md',
  },
  {
    label: 'LLM 제공업체 설정 빠른 참고',
    href: 'https://github.com/ZhuLinsen/daily_stock_analysis/blob/main/docs/llm-providers.md',
  },
];

function HelpLabel({
  htmlFor,
  label,
  fieldKey,
  helpKey,
  examples,
  compact = false,
}: {
  htmlFor?: string;
  label: string;
  fieldKey: string;
  helpKey: string;
  examples?: string[];
  compact?: boolean;
}) {
  return (
    <div className={compact ? 'mb-1 flex items-center gap-1.5' : 'mb-2 flex items-center gap-1.5'}>
      <label
        htmlFor={htmlFor}
        className={compact ? 'text-xs text-muted-text' : 'text-sm font-medium text-foreground'}
      >
        {label}
      </label>
      <SettingsHelpButton
        fieldKey={fieldKey}
        title={label}
        helpKey={helpKey}
        examples={examples}
        docs={LLM_CHANNEL_HELP_DOCS}
      />
    </div>
  );
}

const ChannelRow: React.FC<ChannelRowProps> = ({
  channel,
  index,
  busy,
  visibleKey,
  expanded,
  testState,
  discoveryState,
  capabilityState,
  onUpdate,
  onRemove,
  onToggleExpand,
  onToggleKeyVisibility,
  onTest,
  onDiscoverModels,
  onToggleCapability,
  onCheckCapabilities,
}) => {
  const preset = getProviderTemplate(channel.name);
  const showProviderTemplateDetails = isKnownProviderTemplate(channel.name);
  const displayName = preset?.label || channel.name;
  const providerCapabilities = showProviderTemplateDetails ? (preset?.capabilities || []) : [];
  const providerSources = showProviderTemplateDetails ? (preset?.officialSources || []) : [];
  const providerHint = showProviderTemplateDetails ? preset?.configHint : undefined;
  const selectedModels = splitModels(channel.models);
  const discoveredModels = discoveryState?.models || [];
  const manualOnlyModels = selectedModels.filter(
    (model) => !discoveredModels.some((discoveredModel) => areModelsEquivalent(model, discoveredModel, channel.protocol)),
  );
  const modelCount = selectedModels.length;
  const hasKey = channel.apiKey.length > 0;
  const statusVariant = testState?.status === 'success'
    ? 'success'
    : testState?.status === 'error'
      ? 'danger'
      : testState?.status === 'loading'
        ? 'warning'
        : 'default';
  const selectedCapabilities = capabilityState?.selected || [];
  const capabilityResults = capabilityState?.results || {};
  const capabilityBusy = capabilityState?.status === 'loading';
  const channelNameInputId = `llm-channel-${channel.id}-name`;
  const protocolInputId = `llm-channel-${channel.id}-protocol`;
  const baseUrlInputId = `llm-channel-${channel.id}-base-url`;
  const apiKeyInputId = `llm-channel-${channel.id}-api-key`;
  const modelsInputId = `llm-channel-${channel.id}-models`;

  return (
    <div className="mb-2 overflow-hidden rounded-xl border border-[var(--settings-border)] bg-[var(--settings-surface)] shadow-soft-card transition-[background-color,border-color,box-shadow] duration-200 hover:border-[var(--settings-border-strong)] hover:bg-[var(--settings-surface-hover)]">
      <div
        className="flex cursor-pointer select-none items-center gap-2.5 px-4 py-3 transition-colors"
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
            {modelCount > 0 ? `${modelCount} 개 모델 설정됨` : '모델 미설정'}
          </p>
        </div>

        <span className="flex shrink-0 items-center gap-2">
          {testState?.status === 'success' ? (
            <Tooltip content="연결 정상">
              <span className="inline-flex">
                <StatusDot tone="success" />
              </span>
            </Tooltip>
          ) : null}
          {testState?.status === 'error' ? (
            <Tooltip content="연결 실패">
              <span className="inline-flex">
                <StatusDot tone="danger" />
              </span>
            </Tooltip>
          ) : null}
          {testState?.status === 'loading' ? (
            <Tooltip content="테스트 중">
              <span className="inline-flex">
                <StatusDot tone="warning" pulse />
              </span>
            </Tooltip>
          ) : null}
          {!hasKey && channel.protocol !== 'ollama' ? <Badge variant="warning">Key 미입력</Badge> : null}
          {testState?.status !== 'idle' ? (
            <Badge variant={statusVariant}>
              {testState?.status === 'success' ? '연결 정상' : testState?.status === 'error' ? '연결 실패' : '테스트 중'}
            </Badge>
          ) : null}
        </span>

        <Tooltip content="채널 삭제">
          <span className="inline-flex">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8 shrink-0 px-2 text-xs text-muted-text hover:text-rose-300"
              disabled={busy}
              onClick={(e) => {
                e.stopPropagation();
                onRemove(index);
              }}
            >
              ✕
            </Button>
          </span>
        </Tooltip>
      </div>

      {expanded ? (
        <div className="settings-surface-overlay-soft space-y-4 px-4 py-4">
          <div className="grid gap-2 sm:grid-cols-2">
            <div>
              <HelpLabel
                htmlFor={channelNameInputId}
                label="채널 이름"
                fieldKey="LLM_CHANNEL_NAME"
                helpKey="settings.llm_channel.channel_name"
                examples={['LLM_CHANNELS=deepseek,aihubmix', 'LLM_DEEPSEEK_MODELS=deepseek-v4-flash,deepseek-v4-pro']}
              />
            <Input
              id={channelNameInputId}
              value={channel.name}
              disabled={busy}
              onChange={(e) => onUpdate(index, 'name', e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ''))}
              placeholder="primary"
            />
            </div>
            <div className="space-y-2">
              <HelpLabel
                htmlFor={protocolInputId}
                label="프로토콜"
                fieldKey="LLM_CHANNEL_PROTOCOL"
                helpKey="settings.llm_channel.protocol"
                examples={['LLM_DEEPSEEK_PROTOCOL=deepseek', 'LLM_OPENROUTER_PROTOCOL=openai']}
              />
              <Select
                id={protocolInputId}
                value={channel.protocol}
                onChange={(v) => onUpdate(index, 'protocol', normalizeProtocol(v))}
                options={PROTOCOL_OPTIONS}
                disabled={busy}
                placeholder="프로토콜 선택"
              />
            </div>
          </div>

          <div>
            <HelpLabel
              htmlFor={baseUrlInputId}
              label="Base URL"
              fieldKey="LLM_CHANNEL_BASE_URL"
              helpKey="settings.llm_channel.base_url"
              examples={['LLM_DEEPSEEK_BASE_URL=https://api.deepseek.com', 'LLM_OPENROUTER_BASE_URL=https://openrouter.ai/api/v1']}
            />
          <Input
            id={baseUrlInputId}
            value={channel.baseUrl}
            disabled={busy}
            onChange={(e) => onUpdate(index, 'baseUrl', e.target.value)}
            placeholder={
              channel.protocol === 'gemini' || channel.protocol === 'anthropic'
                ? '공식 API는 비워둘 수 있습니다'
                : preset?.baseUrl || 'https://api.example.com/v1'
            }
          />
          </div>

          {showProviderTemplateDetails ? (
            <div className="space-y-2 rounded-xl border border-[var(--settings-border)] bg-[var(--settings-surface-hover)] p-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[11px] font-medium text-muted-text">설정 참고</span>
                {providerCapabilities.map((capability) => {
                  const capabilityMeta = LLM_PROVIDER_CAPABILITY_LABELS[capability];
                  return (
                    <Tooltip key={capability} content={capabilityMeta.hint}>
                      <span className="inline-flex">
                        <Badge variant="default" className="border-[var(--settings-border)] bg-[var(--settings-surface)] text-secondary-text">
                          {capabilityMeta.label}
                        </Badge>
                      </span>
                    </Tooltip>
                  );
                })}
              </div>
              {providerHint ? (
                <p className="text-[11px] leading-5 text-secondary-text">{providerHint}</p>
              ) : null}
              {providerSources.length > 0 ? (
                <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] leading-5 text-secondary-text">
                  <span>공식 출처: </span>
                  {providerSources.map((source) => (
                    <a
                      key={source.url}
                      href={source.url}
                      target="_blank"
                      rel="noreferrer"
                      className="settings-accent-text underline-offset-2 hover:underline"
                    >
                      {source.label}
                    </a>
                  ))}
                </p>
              ) : null}
              <p className="text-[11px] leading-5 text-muted-text">
                기능 태그는 설정 참고용이며 런타임 기능 검증 통과를 의미하지 않습니다.
              </p>
            </div>
          ) : null}

          <div>
            <HelpLabel
              htmlFor={apiKeyInputId}
              label="API Key"
              fieldKey="LLM_CHANNEL_API_KEY"
              helpKey="settings.llm_channel.api_key"
              examples={['LLM_DEEPSEEK_API_KEY=sk-xxxx', 'LLM_OPENAI_API_KEYS=sk-key-1,sk-key-2']}
            />
          <Input
            id={apiKeyInputId}
            type="password"
            allowTogglePassword
            iconType="key"
            passwordVisible={visibleKey}
            onPasswordVisibleChange={(nextVisible) => onToggleKeyVisibility(index, nextVisible)}
            value={channel.apiKey}
            disabled={busy}
            onChange={(e) => onUpdate(index, 'apiKey', e.target.value)}
            placeholder={channel.protocol === 'ollama' ? '로컬 Ollama는 비워둘 수 있습니다' : '여러 Key는 쉼표로 구분'}
          />
          </div>

          <div className="space-y-3 rounded-xl border border-[var(--settings-border)] bg-[var(--settings-surface-hover)] p-3">
            <div className="flex flex-wrap items-center gap-2">
              <Button
                type="button"
                variant="settings-secondary"
                size="sm"
                className="px-3 text-[11px] shadow-none"
                disabled={busy}
                onClick={() => onDiscoverModels(channel)}
              >
                {discoveryState?.status === 'loading' ? '가져오는 중...' : '모델 가져오기'}
              </Button>
              <span className={`text-xs ${
                discoveryState?.status === 'success'
                  ? 'text-success'
                  : discoveryState?.status === 'error'
                    ? 'text-danger'
                    : 'text-muted-text'
              }`}
              >
                {discoveryState?.text || '`/models`를 지원하는 OpenAI Compatible 채널은 모델 목록을 자동으로 가져올 수 있습니다.'}
              </span>
            </div>
            {discoveryState?.hint ? (
              <p className="text-[11px] text-secondary-text">
                {discoveryState.hint}
              </p>
            ) : null}

            {discoveredModels.length > 0 ? (
              <div>
                <HelpLabel
                  label="선택 가능한 모델(복수 선택 가능)"
                  fieldKey="LLM_CHANNEL_DISCOVERED_MODELS"
                  helpKey="settings.llm_channel.models"
                  examples={['LLM_DEEPSEEK_MODELS=deepseek-v4-flash,deepseek-v4-pro']}
                />
                <div className="max-h-48 space-y-2 overflow-y-auto rounded-xl border border-[var(--settings-border)] bg-[var(--settings-surface)] p-3">
                  {discoveredModels.map((model) => (
                    <label key={model} className="flex items-center gap-2 text-sm text-secondary-text">
                      <input
                        type="checkbox"
                        checked={selectedModels.some((selectedModel) => (
                          areModelsEquivalent(selectedModel, model, channel.protocol)
                        ))}
                        disabled={busy}
                        onChange={() => onUpdate(index, 'models', toggleModelSelection(channel.models, model, channel.protocol))}
                        className="settings-input-checkbox h-4 w-4 rounded border-border/70 bg-base"
                      />
                      <span>{model}</span>
                    </label>
                  ))}
                </div>
              </div>
            ) : null}

            <div>
              <HelpLabel
                htmlFor={modelsInputId}
                label={discoveredModels.length > 0 ? '수동 모델(쉼표 구분)' : '모델(쉼표 구분)'}
                fieldKey="LLM_CHANNEL_MODELS"
                helpKey="settings.llm_channel.models"
                examples={['LLM_DEEPSEEK_MODELS=deepseek-v4-flash,deepseek-v4-pro', 'LLM_OLLAMA_MODELS=qwen3:8b,llama3.1:8b']}
              />
            <Input
              id={modelsInputId}
              value={channel.models}
              disabled={busy}
              onChange={(e) => onUpdate(index, 'models', e.target.value)}
              placeholder={preset?.placeholderModels || MODEL_PLACEHOLDERS_BY_PROTOCOL[channel.protocol]}
              hint={
                discoveredModels.length > 0
                  ? '사용자 정의 모델명이 목록에 없으면 수동으로 추가할 수 있으며, 저장 형식은 쉼표 구분입니다.'
                  : '채널이 자동 검색을 지원하지 않거나 요청이 실패하면 모델 목록을 직접 입력하세요.'
              }
            />
            </div>

            {manualOnlyModels.length > 0 ? (
              <p className="text-[11px] text-secondary-text">
                추가 수동 모델: {manualOnlyModels.join(', ')}
              </p>
            ) : null}
          </div>

          <div className="flex items-center gap-2 pt-1">
            <Button
              type="button"
              variant="settings-secondary"
              size="sm"
              className="px-3 text-[11px] shadow-none"
              disabled={busy}
              onClick={() => onTest(channel, index)}
            >
              {testState?.status === 'loading' ? '테스트 중...' : '연결 테스트'}
            </Button>
            {testState?.text ? (
              <div className="space-y-1">
                <span className={`block text-xs ${
                  testState.status === 'success'
                    ? 'text-success'
                    : testState.status === 'error'
                      ? 'text-danger'
                      : 'text-muted-text'
                }`}
                >
                  {testState.text}
                </span>
                {selectedModels[0] ? (
                  <p className="text-[11px] text-secondary-text">
                    기본 연결 테스트는 모델 목록의 첫 항목을 사용합니다: {selectedModels[0]}
                  </p>
                ) : null}
                {testState.hint ? (
                  <p className="text-[11px] text-secondary-text">
                    {testState.hint}
                  </p>
                ) : null}
              </div>
            ) : null}
          </div>

          <div className="space-y-3 rounded-xl border border-[var(--settings-border)] bg-[var(--settings-surface-hover)] p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <div className="flex items-center gap-1.5">
                  <p className="text-[11px] font-medium text-muted-text">런타임 기능 검사(선택)</p>
                  <SettingsHelpButton
                    fieldKey="LLM_CHANNEL_CAPABILITY_CHECKS"
                    title="런타임 기능 검사"
                    helpKey="settings.llm_channel.capability_checks"
                    examples={['JSON / Tools / Stream / Vision']}
                    docs={LLM_CHANNEL_HELP_DOCS}
                  />
                </div>
                <p className="mt-0.5 text-[11px] text-secondary-text">
                  수동 실행 시에만 실제 LLM 요청을 보냅니다. 복수 선택은 20-40초가 걸릴 수 있습니다.
                </p>
              </div>
              <Button
                type="button"
                variant="settings-secondary"
                size="sm"
                className="px-3 text-[11px] shadow-none"
                disabled={busy || capabilityBusy || selectedCapabilities.length === 0}
                onClick={() => onCheckCapabilities(channel)}
              >
                {capabilityBusy ? '검사 중...' : '기능 검사'}
              </Button>
            </div>

            <div className="flex flex-wrap gap-2">
              {RUNTIME_CAPABILITY_OPTIONS.map((option) => (
                <Tooltip key={option.value} content={option.hint}>
                  <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-[var(--settings-border)] bg-[var(--settings-surface)] px-2 py-1 text-[11px] text-secondary-text">
                    <input
                      type="checkbox"
                      checked={selectedCapabilities.includes(option.value)}
                      disabled={busy || capabilityBusy}
                      onChange={() => onToggleCapability(channel, option.value)}
                      className="settings-input-checkbox h-3.5 w-3.5 rounded border-border/70 bg-base"
                    />
                    <span>{option.label}</span>
                  </label>
                </Tooltip>
              ))}
            </div>

            {capabilityState?.text ? (
              <div className="space-y-1">
                <p className={`text-xs ${
                  capabilityState.status === 'success'
                    ? 'text-success'
                    : capabilityState.status === 'error'
                      ? 'text-danger'
                      : 'text-muted-text'
                }`}
                >
                  {capabilityState.text}
                </p>
                {capabilityState.hint ? (
                  <p className="text-[11px] text-secondary-text">{capabilityState.hint}</p>
                ) : null}
              </div>
            ) : null}

            {Object.keys(capabilityResults).length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {RUNTIME_CAPABILITY_OPTIONS.map((option) => {
                  const result = capabilityResults[option.value];
                  if (!result) return null;
                  return (
                    <Tooltip key={option.value} content={result.message}>
                      <span className="inline-flex">
                        <Badge variant={getCapabilityResultVariant(result.status)}>
                          {option.label} {CAPABILITY_STATUS_LABELS[result.status]}
                        </Badge>
                      </span>
                    </Tooltip>
                  );
                })}
              </div>
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

interface ParsedModelRef {
  name: string;
  provider: string;
  hasProvider: boolean;
}

function parseModelRef(model: string): ParsedModelRef {
  const trimmed = model.trim();
  if (!trimmed) {
    return { name: '', provider: '', hasProvider: false };
  }

  const delimiterIndex = trimmed.indexOf('/');
  if (delimiterIndex < 0) {
    return { name: trimmed.toLowerCase(), provider: '', hasProvider: false };
  }

  const rawProvider = trimmed.slice(0, delimiterIndex).trim();
  const name = trimmed.slice(delimiterIndex + 1).trim();
  if (!rawProvider || !name) {
    return { name: '', provider: '', hasProvider: false };
  }

  const lowerProvider = rawProvider.toLowerCase();
  return {
    name: name.toLowerCase(),
    provider: PROTOCOL_ALIASES[lowerProvider] || lowerProvider,
    hasProvider: true,
  };
}

function getModelComparisonKey(model: string, protocol: ChannelProtocol): string {
  const normalizedModel = normalizeModelForRuntime(model, protocol).trim();
  const parsed = parseModelRef(normalizedModel);
  if (!parsed.name) {
    return '';
  }
  return `${parsed.provider}/${parsed.name}`;
}

function areModelsEquivalent(a: string, b: string, protocol: ChannelProtocol): boolean {
  const left = getModelComparisonKey(a, protocol);
  const right = getModelComparisonKey(b, protocol);
  return left !== '' && left === right;
}

function toggleModelSelection(models: string, targetModel: string, protocol: ChannelProtocol): string {
  const selectedModels = splitModels(models);
  const index = selectedModels.findIndex((model) => areModelsEquivalent(model, targetModel, protocol));
  if (index >= 0) {
    return selectedModels.filter((_, itemIndex) => itemIndex !== index).join(',');
  }
  return [...selectedModels, targetModel].join(',');
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
    options.push({ value: selectedModel, label: `${selectedModel}(현재 설정)` });
  }
  for (const model of models) {
    options.push({ value: model, label: model });
  }
  return options;
}

const LLM_STAGE_LABELS: Record<string, string> = {
  model_discovery: '모델 검색',
  chat_completion: '채팅 호출',
  response_parse: '응답 파싱',
  capability_json: 'JSON 기능',
  capability_tools: 'Tools 기능',
  capability_stream: 'Stream 기능',
  capability_vision: 'Vision 기능',
};

const LLM_ERROR_LABELS: Record<string, string> = {
  auth: '인증 실패',
  timeout: '요청 시간 초과',
  quota: '한도 또는 속도 제한',
  model_not_found: '모델 사용 불가',
  request_blocked: '요청 차단됨',
  empty_response: '빈 응답',
  format_error: '형식 오류',
  network_error: '네트워크 오류',
  invalid_config: '설정이 유효하지 않음',
  unsupported_protocol: '프로토콜 미지원',
  capability_unsupported: '기능 미지원',
  skipped: '건너뜀',
};

const LLM_TROUBLESHOOTING_HINTS: Record<string, string> = {
  auth: 'API Key가 올바른지, 불필요한 공백이 있는지, 현재 채널에 추가 조직/프로젝트 권한이 필요한지 확인하세요.',
  timeout: '다시 시도할 수 있습니다. 계속 시간 초과가 발생하면 Base URL, 네트워크 프록시, 제공업체 가용 영역 또는 로컬 방화벽을 확인하세요.',
  quota: '잔액, 요금제 한도, RPM/TPM 제한 또는 동시성 설정을 확인하고 필요하면 잠시 후 다시 시도하세요.',
  model_not_found: '모델명이 채널 프로토콜과 맞는지 확인하고 먼저 “모델 가져오기”로 실제 사용 가능한 모델 목록을 확인하세요.',
  empty_response: '채널은 연결되었지만 본문을 반환하지 않았습니다. 호환 모델로 바꾸거나 추가 응답 모드를 끈 뒤 다시 테스트하세요.',
  network_error: 'Base URL, 프록시, TLS/인증서, 중계 게이트웨이 또는 로컬 네트워크 정책을 확인하고 잠시 후 다시 시도하세요.',
  invalid_config: '프로토콜, Base URL, API Key, 모델 설정을 먼저 채운 뒤 일괄 테스트를 실행하세요.',
  unsupported_protocol: '현재 자동 모델 검색은 OpenAI Compatible / DeepSeek 채널에만 제공됩니다. 모델 목록을 수동으로 관리하세요.',
};

const LLM_REASON_HINTS: Record<string, string> = {
  missing_api_key: 'API Key가 비어 있거나 쉼표로 나눈 뒤 사용 가능한 Key가 없습니다. 최소 하나의 유효한 Key를 입력한 뒤 테스트하세요.',
  api_key_rejected: '제공업체가 현재 API Key를 거부했습니다. Key, 조직/프로젝트 권한, 지역, 계정 상태를 확인하세요.',
  rate_limit: '제공업체의 RPM/TPM 또는 동시성 제한에 걸렸습니다. 요청 빈도를 낮추거나 잠시 후 다시 시도하세요.',
  insufficient_balance: '제공업체가 잔액, 결제 또는 한도 부족을 반환했습니다. 계정 잔액과 요금제 상태를 확인하세요.',
  quota_exceeded: '제공업체의 할당량이 소진되었습니다. 계정 요금제, 남은 한도, 프로젝트 한도를 확인하세요.',
  provider_blocked: '요청이 제공업체 또는 중계 게이트웨이에 의해 차단되었습니다. 계정 리스크 제어, 지역 제한, 모델 권한, 게이트웨이 정책, 콘텐츠 안전 정책 또는 요청 출처 제한을 확인하세요.',
  dns_error: '도메인 해석 실패입니다. Base URL 도메인, 네트워크 프록시, DNS 설정을 확인하세요.',
  tls_error: 'TLS/인증서 핸드셰이크 실패입니다. HTTPS 인증서, 중계 게이트웨이 또는 회사 프록시 정책을 확인하세요.',
  connection_refused: '대상 서비스가 연결을 거부했습니다. Base URL 포트, 서비스 프로세스, 방화벽 설정을 확인하세요.',
  model_access_denied: '현재 계정으로 해당 모델을 사용할 수 없습니다. 모델 사용 권한, 계정 노출 여부, 모델 비활성화 여부를 확인하세요.',
  provider_prefix_mismatch: '모델 provider 접두사가 현재 채널과 맞지 않습니다. 모델명이 이 채널의 OpenAI-compatible 라우팅을 사용해야 하는지 확인하세요.',
  capability_unsupported: '현재 모델 또는 호환 계층이 이 기능을 지원하지 않습니다. 기본 텍스트 연결에는 영향이 없으며, 모델을 바꾸거나 해당 기능 의존성을 끌 수 있습니다.',
};

function getLlmStageLabel(stage?: string | null): string {
  return LLM_STAGE_LABELS[stage || ''] || '연결 테스트';
}

function getLlmErrorCodeLabel(code?: string | null): string {
  return LLM_ERROR_LABELS[code || ''] || '테스트 실패';
}

function getLlmTroubleshootingHint(
  code?: string | null,
  stage?: string | null,
  context: 'test' | 'discovery' = 'test',
  details?: Record<string, unknown>,
): string | undefined {
  const reason = typeof details?.reason === 'string' ? details.reason : '';
  if (reason && LLM_REASON_HINTS[reason]) {
    return LLM_REASON_HINTS[reason];
  }
  if (code === 'format_error') {
    return context === 'discovery' || stage === 'model_discovery'
      ? '이 채널의 /models 응답 형식이 호환되지 않습니다. 모델 목록을 수동으로 입력하세요.'
      : '반환 구조가 예상과 다릅니다. 해당 채널이 Chat Completions API와 호환되는지 확인하세요.';
  }
  if (code === 'empty_response' && (context === 'discovery' || stage === 'model_discovery')) {
    return '이 채널의 /models API가 사용 가능한 모델 ID를 반환하지 않았습니다. Base URL이 호환 모델 목록 API를 가리키는지 확인하거나 모델 목록을 수동으로 입력하세요.';
  }
  return LLM_TROUBLESHOOTING_HINTS[code || ''];
}

function buildLlmTestHint(result: {
  errorCode?: string | null;
  stage?: string | null;
  details?: Record<string, unknown>;
  resolvedModel?: string | null;
}): string | undefined {
  const reason = typeof result.details?.reason === 'string' ? result.details.reason : '';
  const detailsModel = typeof result.details?.model === 'string' ? result.details.model : '';
  const testedModel = result.resolvedModel || detailsModel;
  const modelHint = testedModel ? `이번 테스트 모델: ${testedModel}.` : '';
  const scopeInfo = '기본 연결 테스트는 모델 목록의 첫 번째 모델만 테스트합니다.';
  const shouldSuggestModelListChange = reason === 'model_access_denied'
    || reason === 'model_not_found'
    || (result.errorCode === 'model_not_found' && !reason);
  const modelActionHint = shouldSuggestModelListChange
    ? '해당 모델을 사용할 수 없으면 모델 순서를 조정하거나 사용할 수 없는 모델을 제거한 뒤 다시 시도하세요.'
    : '';
  const troubleshootingHint = getLlmTroubleshootingHint(result.errorCode, result.stage, 'test', result.details);
  return [modelHint, scopeInfo, modelActionHint, troubleshootingHint].filter(Boolean).join(' ') || undefined;
}

function buildLlmFailureText(result: {
  message: string;
  error?: string | null;
  stage?: string | null;
  errorCode?: string | null;
}): string {
  const prefix = `${getLlmStageLabel(result.stage)} · ${getLlmErrorCodeLabel(result.errorCode)}`;
  const summary = result.message || '테스트 실패';
  if (result.error && result.error !== result.message) {
    return `${prefix}: ${summary}(원본 요약: ${result.error})`;
  }
  return `${prefix}: ${summary}`;
}

function getCapabilityResultVariant(status: LLMCapabilityCheckResult['status']): 'success' | 'danger' | 'warning' {
  if (status === 'passed') return 'success';
  if (status === 'skipped') return 'warning';
  return 'danger';
}

function summarizeCapabilityResults(results: Partial<Record<LLMCapabilityCheck, LLMCapabilityCheckResult>>): string {
  const values = Object.values(results);
  const passed = values.filter((result) => result?.status === 'passed').length;
  const failed = values.filter((result) => result?.status === 'failed').length;
  const skipped = values.filter((result) => result?.status === 'skipped').length;
  return `기능 검사 완료: ${passed} 통과 / ${failed} 실패 / ${skipped} 건너뜀`;
}

function getFirstCapabilityHint(
  results: Partial<Record<LLMCapabilityCheck, LLMCapabilityCheckResult>>,
): string | undefined {
  for (const result of Object.values(results)) {
    if (!result || result.status === 'passed') continue;
    const hint = getLlmTroubleshootingHint(result.errorCode, result.stage, 'test', result.details);
    if (hint) return hint;
  }
  return undefined;
}

const MANAGED_PROVIDERS = new Set(['gemini', 'vertex_ai', 'anthropic', 'openai', 'deepseek']);
const LEGACY_PROVIDER_KEYS: Record<string, string[]> = {
  gemini: ['GEMINI_API_KEYS', 'GEMINI_API_KEY'],
  vertex_ai: ['GEMINI_API_KEYS', 'GEMINI_API_KEY'],
  anthropic: ['ANTHROPIC_API_KEYS', 'ANTHROPIC_API_KEY'],
  openai: ['OPENAI_API_KEYS', 'AIHUBMIX_KEY', 'OPENAI_API_KEY'],
  deepseek: ['DEEPSEEK_API_KEYS', 'DEEPSEEK_API_KEY'],
};

function getRuntimeProvider(model: string): string {
  if (!model) return '';
  if (!model.includes('/')) return 'openai';
  return model.split('/', 1)[0].trim().toLowerCase();
}

function usesDirectEnvProvider(model: string): boolean {
  const provider = getRuntimeProvider(model);
  return Boolean(provider) && !MANAGED_PROVIDERS.has(provider);
}

function hasLegacyRuntimeSource(model: string, itemMap: Map<string, string>): boolean {
  const provider = PROTOCOL_ALIASES[getRuntimeProvider(model)] || getRuntimeProvider(model);
  if (!provider || !MANAGED_PROVIDERS.has(provider)) {
    return false;
  }
  return (LEGACY_PROVIDER_KEYS[provider] || []).some((key) => (itemMap.get(key) || '').trim().length > 0);
}

function isRuntimeModelAvailable(model: string, availableModels: string[], itemMap: Map<string, string>): boolean {
  return availableModels.includes(model)
    || usesDirectEnvProvider(model)
    || (availableModels.length === 0 && hasLegacyRuntimeSource(model, itemMap));
}

function sanitizeRuntimeConfigForSave(
  runtimeConfig: RuntimeConfig,
  availableModels: string[],
  itemMap: Map<string, string>,
): RuntimeConfig {
  const primaryModel = runtimeConfig.primaryModel && !isRuntimeModelAvailable(runtimeConfig.primaryModel, availableModels, itemMap)
    ? ''
    : runtimeConfig.primaryModel;
  const agentPrimaryModel = runtimeConfig.agentPrimaryModel && !isRuntimeModelAvailable(runtimeConfig.agentPrimaryModel, availableModels, itemMap)
    ? ''
    : runtimeConfig.agentPrimaryModel;
  const visionModel = runtimeConfig.visionModel && !isRuntimeModelAvailable(runtimeConfig.visionModel, availableModels, itemMap)
    ? ''
    : runtimeConfig.visionModel;
  const fallbackModels = runtimeConfig.fallbackModels.filter((model) => isRuntimeModelAvailable(model, availableModels, itemMap));

  return {
    ...runtimeConfig,
    primaryModel,
    agentPrimaryModel,
    fallbackModels,
    visionModel,
  };
}

function runtimeConfigsAreEqual(left: RuntimeConfig, right: RuntimeConfig): boolean {
  return left.primaryModel === right.primaryModel
    && left.agentPrimaryModel === right.agentPrimaryModel
    && left.visionModel === right.visionModel
    && left.temperature === right.temperature
    && left.fallbackModels.join(',') === right.fallbackModels.join(',');
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

  return channelNames.map((name, index) => {
    const upperName = name.toUpperCase();
    const baseUrl = itemMap.get(`LLM_${upperName}_BASE_URL`) || '';
    const rawModels = itemMap.get(`LLM_${upperName}_MODELS`) || '';
    const models = splitModels(rawModels);

    return {
      id: `parsed:${index}:${upperName}`,
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

export const LLMChannelEditor: React.FC<LLMChannelEditorProps> = ({
  items,
  configVersion,
  maskToken,
  onSaved,
  disabled = false,
}) => {
  const initialChannels = useMemo(() => parseChannelsFromItems(items), [items]);
  const initialNames = useMemo(() => initialChannels.map((channel) => channel.name), [initialChannels]);
  const initialRuntimeConfig = useMemo(() => parseRuntimeConfigFromItems(items), [items]);
  const savedItemMap = useMemo(() => new Map(items.map((item) => [item.key.toUpperCase(), item.value])), [items]);
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
  const [saveWarnings, setSaveWarnings] = useState<string[]>([]);
  const [visibleKeys, setVisibleKeys] = useState<Record<number, boolean>>({});
  const [testStates, setTestStates] = useState<Record<number, ChannelTestState>>({});
  const [discoveryStates, setDiscoveryStates] = useState<Record<string, ChannelDiscoveryState>>({});
  const [capabilityStates, setCapabilityStates] = useState<Record<string, ChannelCapabilityState>>({});
  const [expandedRows, setExpandedRows] = useState<Record<number, boolean>>({});
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [addPreset, setAddPreset] = useState('aihubmix');
  const addChannelIdRef = useRef(0);

  const prevChannelsRef = useRef(channelsFingerprint);
  const prevRuntimeRef = useRef(runtimeFingerprint);
  const pendingSaveFeedbackFingerprintRef = useRef<{ channels: string; runtime: string } | null>(null);
  const discoveryNonceRef = useRef<Record<string, number>>({});
  const discoveryRequestIdRef = useRef(0);
  const capabilityNonceRef = useRef<Record<string, number>>({});
  const capabilityRequestIdRef = useRef(0);

  useEffect(() => {
    if (prevChannelsRef.current === channelsFingerprint && prevRuntimeRef.current === runtimeFingerprint) {
      return;
    }
    prevChannelsRef.current = channelsFingerprint;
    prevRuntimeRef.current = runtimeFingerprint;
    const pendingSaveFeedbackFingerprint = pendingSaveFeedbackFingerprintRef.current;
    const preserveSaveFeedback = pendingSaveFeedbackFingerprint?.channels === channelsFingerprint
      && pendingSaveFeedbackFingerprint.runtime === runtimeFingerprint;
    pendingSaveFeedbackFingerprintRef.current = null;
    setChannels(initialChannels);
    setRuntimeConfig(initialRuntimeConfig);
    setVisibleKeys({});
    setTestStates({});
    setDiscoveryStates({});
    setCapabilityStates({});
    setExpandedRows({});
    discoveryNonceRef.current = {};
    capabilityNonceRef.current = {};
    if (!preserveSaveFeedback) {
      setSaveMessage(null);
      setSaveWarnings([]);
    }
    setIsCollapsed(false);
  }, [channelsFingerprint, runtimeFingerprint, initialChannels, initialRuntimeConfig]);

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

  const busy = disabled || isSaving;

  const updateChannel = (index: number, field: keyof ChannelConfig, value: string | boolean) => {
    const currentChannel = channels[index];
    setChannels((previous) => previous.map((channel, rowIndex) => {
      if (rowIndex !== index) return channel;
      const updated = { ...channel, [field]: value };

      if (field === 'name' && typeof value === 'string') {
        const newPreset = getProviderTemplate(value);
        if (newPreset) {
          const oldPreset = getProviderTemplate(channel.name);
          if (!updated.baseUrl || updated.baseUrl === (oldPreset?.baseUrl ?? '')) {
            updated.baseUrl = newPreset.baseUrl;
          }
          updated.protocol = newPreset.protocol;
          if (!updated.models || updated.models === (oldPreset?.placeholderModels ?? '')) {
            updated.models = newPreset.placeholderModels;
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
    if (field !== 'models' && field !== 'enabled') {
      setDiscoveryStates((previous) => {
        const channel = channels.find((_, itemIndex) => itemIndex === index);
        if (!channel || !(channel.id in previous)) {
          return previous;
        }
        const next = { ...previous };
        delete next[channel.id];
        delete discoveryNonceRef.current[channel.id];
        return next;
      });
    }
    if (currentChannel) {
      delete capabilityNonceRef.current[currentChannel.id];
      setCapabilityStates((previous) => {
        const current = previous[currentChannel.id];
        if (!current) {
          return previous;
        }
        return {
          ...previous,
          [currentChannel.id]: {
            ...current,
            status: 'idle',
            text: undefined,
            hint: undefined,
            results: {},
          },
        };
      });
    }
  };

  const removeChannel = (index: number) => {
    const removedChannelId = channels[index]?.id || '';
    setChannels((previous) => previous.filter((_, rowIndex) => rowIndex !== index));
    setVisibleKeys({});
    setTestStates({});
    setDiscoveryStates((previous) => {
      if (!removedChannelId) {
        return previous;
      }
      const next = { ...previous };
      delete next[removedChannelId];
      return next;
    });
    setCapabilityStates((previous) => {
      if (!removedChannelId || !(removedChannelId in previous)) {
        return previous;
      }
      const next = { ...previous };
      delete next[removedChannelId];
      return next;
    });
    if (removedChannelId) {
      const nextNonce = { ...discoveryNonceRef.current };
      delete nextNonce[removedChannelId];
      discoveryNonceRef.current = nextNonce;
      delete capabilityNonceRef.current[removedChannelId];
    }
    setExpandedRows({});
  };

  const addChannel = () => {
    const preset = getProviderTemplate(addPreset) || getProviderTemplate('custom');
    if (!preset) {
      return;
    }
    setChannels((previous) => {
      const existingNames = new Set(previous.map((channel) => channel.name));
      const baseName = addPreset === 'custom' ? 'custom' : addPreset;
      let nextName = baseName;
      let counter = 2;
      while (existingNames.has(nextName)) {
        nextName = `${baseName}${counter}`;
        counter += 1;
      }

      return [
        ...previous,
        {
          id: `added:${addChannelIdRef.current += 1}`,
          name: nextName,
          protocol: preset.protocol,
          baseUrl: preset.baseUrl,
          apiKey: '',
          models: preset.placeholderModels || '',
          enabled: true,
        },
      ];
    });
    setTestStates({});
    setDiscoveryStates({});
    setCapabilityStates({});
    discoveryNonceRef.current = {};
    capabilityNonceRef.current = {};
    setExpandedRows((prev) => ({ ...prev, [channels.length]: true }));
    setIsCollapsed(false);
  };

  const handleSave = async () => {
    const hasEmptyName = channels.some((channel) => !channel.name.trim());
    if (hasEmptyName) {
      setSaveMessage({ type: 'local-error', text: '채널 이름은 비워둘 수 없으며 영문자, 숫자, 밑줄만 사용할 수 있습니다.' });
      return;
    }

    const runtimeConfigForSave = managesRuntimeConfig
      ? sanitizeRuntimeConfigForSave(runtimeConfig, availableModels, savedItemMap)
      : runtimeConfig;
    if (!runtimeConfigsAreEqual(runtimeConfigForSave, runtimeConfig)) {
      setRuntimeConfig(runtimeConfigForSave);
    }

    if (managesRuntimeConfig) {
      const invalidPrimaryModel = runtimeConfigForSave.primaryModel
        && !isRuntimeModelAvailable(runtimeConfigForSave.primaryModel, availableModels, savedItemMap);
      if (invalidPrimaryModel) {
        setSaveMessage({ type: 'local-error', text: '현재 기본 모델이 활성 채널의 모델 목록에 없습니다. 다시 선택하세요.' });
        return;
      }

      const invalidAgentPrimaryModel = runtimeConfigForSave.agentPrimaryModel
        && !isRuntimeModelAvailable(runtimeConfigForSave.agentPrimaryModel, availableModels, savedItemMap);
      if (invalidAgentPrimaryModel) {
        setSaveMessage({ type: 'local-error', text: '현재 Agent 기본 모델이 활성 채널의 모델 목록에 없습니다. 다시 선택하세요.' });
        return;
      }

      const invalidFallbackModel = runtimeConfigForSave.fallbackModels.some(
        (model) => !isRuntimeModelAvailable(model, availableModels, savedItemMap),
      );
      if (invalidFallbackModel) {
        setSaveMessage({ type: 'local-error', text: '유효하지 않은 대체 모델이 있습니다. 다시 선택하세요.' });
        return;
      }

      const invalidVisionModel = runtimeConfigForSave.visionModel
        && !isRuntimeModelAvailable(runtimeConfigForSave.visionModel, availableModels, savedItemMap);
      if (invalidVisionModel) {
        setSaveMessage({ type: 'local-error', text: '현재 Vision 모델이 활성 채널의 모델 목록에 없습니다. 다시 선택하세요.' });
        return;
      }
    }

    setIsSaving(true);
    setSaveMessage(null);
    setSaveWarnings([]);

    try {
      const updateItems = channelsToUpdateItems(channels, initialNames, runtimeConfigForSave, managesRuntimeConfig);
      const response = await systemConfigApi.update({
        configVersion,
        maskToken,
        reloadNow: true,
        items: updateItems,
      });
      const responseWarnings = response.warnings || [];
      await onSaved(updateItems);
      pendingSaveFeedbackFingerprintRef.current = {
        channels: JSON.stringify(parseChannelsFromItems(updateItems)),
        runtime: JSON.stringify(parseRuntimeConfigFromItems(updateItems)),
      };
      setSaveWarnings(responseWarnings);
      setSaveMessage({ type: 'success', text: managesRuntimeConfig ? 'AI 설정이 저장되었습니다' : '채널 설정이 저장되었습니다' });
    } catch (error: unknown) {
      setSaveWarnings([]);
      setSaveMessage({ type: 'error', error: getParsedApiError(error) });
    } finally {
      setIsSaving(false);
    }
  };

  const handleTest = async (channel: ChannelConfig, index: number) => {
    setTestStates((previous) => ({
      ...previous,
      [index]: { status: 'loading', text: '테스트 중...' },
    }));

    try {
      const result = await systemConfigApi.testLLMChannel({
        name: channel.name,
        protocol: channel.protocol,
        baseUrl: channel.baseUrl,
        apiKey: channel.apiKey,
        models: splitModels(channel.models),
        enabled: channel.enabled,
      });

      const text = result.success
        ? `연결 성공${result.resolvedModel ? ` · ${result.resolvedModel}` : ''}${result.latencyMs ? ` · ${result.latencyMs} ms` : ''}`
        : buildLlmFailureText(result);
      const hint = result.success ? undefined : buildLlmTestHint(result);

      setTestStates((previous) => ({
        ...previous,
        [index]: {
          status: result.success ? 'success' : 'error',
          text,
          hint,
        },
      }));
    } catch (error: unknown) {
      const parsed = getParsedApiError(error);
      setTestStates((previous) => ({
        ...previous,
        [index]: { status: 'error', text: parsed.message || '테스트 실패' },
      }));
    }
  };

  const handleDiscoverModels = async (channel: ChannelConfig) => {
    const requestId = discoveryRequestIdRef.current + 1;
    discoveryRequestIdRef.current = requestId;
    discoveryNonceRef.current[channel.id] = requestId;
    const nonce = requestId;

    setDiscoveryStates((previous) => ({
      ...previous,
      [channel.id]: {
        status: 'loading',
        text: '모델 목록을 가져오는 중...',
        hint: undefined,
        models: previous[channel.id]?.models || [],
      },
    }));

    try {
      const result = await systemConfigApi.discoverLLMChannelModels({
        name: channel.name,
        protocol: channel.protocol,
        baseUrl: channel.baseUrl,
        apiKey: channel.apiKey,
        models: splitModels(channel.models),
      });

      if (discoveryNonceRef.current[channel.id] !== nonce) return;

      setDiscoveryStates((previous) => ({
        ...previous,
        [channel.id]: {
          status: result.success ? 'success' : 'error',
          text: result.success
            ? `가져옴 ${result.models.length} 개 모델${result.latencyMs ? ` · ${result.latencyMs} ms` : ''}`
            : buildLlmFailureText(result),
          hint: result.success ? undefined : getLlmTroubleshootingHint(result.errorCode, result.stage, 'discovery', result.details),
          models: result.success ? result.models : (previous[channel.id]?.models || []),
        },
      }));
    } catch (error: unknown) {
      if (discoveryNonceRef.current[channel.id] !== nonce) return;

      const parsed = getParsedApiError(error);
      setDiscoveryStates((previous) => ({
        ...previous,
        [channel.id]: {
          status: 'error',
          text: parsed.message || '모델 가져오기실패',
          hint: undefined,
          models: previous[channel.id]?.models || [],
        },
      }));
    }
  };

  const toggleCapability = (channel: ChannelConfig, capability: LLMCapabilityCheck) => {
    setCapabilityStates((previous) => {
      const current = previous[channel.id] || { selected: [], status: 'idle', results: {} };
      const selected = current.selected.includes(capability)
        ? current.selected.filter((item) => item !== capability)
        : [...current.selected, capability];
      return {
        ...previous,
        [channel.id]: {
          ...current,
          selected,
          status: current.status === 'loading' ? current.status : 'idle',
          text: current.status === 'loading' ? current.text : undefined,
          hint: current.status === 'loading' ? current.hint : undefined,
          results: current.status === 'loading' ? current.results : {},
        },
      };
    });
  };

  const handleCapabilityCheck = async (channel: ChannelConfig) => {
    const selected = capabilityStates[channel.id]?.selected || [];
    if (selected.length === 0) return;

    const requestId = capabilityRequestIdRef.current + 1;
    capabilityRequestIdRef.current = requestId;
    capabilityNonceRef.current[channel.id] = requestId;
    const nonce = requestId;

    setCapabilityStates((previous) => ({
      ...previous,
      [channel.id]: {
        selected,
        status: 'loading',
        text: '런타임 기능 검사 중...',
        hint: undefined,
        results: {},
      },
    }));

    try {
      const result = await systemConfigApi.testLLMChannel({
        name: channel.name,
        protocol: channel.protocol,
        baseUrl: channel.baseUrl,
        apiKey: channel.apiKey,
        models: splitModels(channel.models),
        enabled: channel.enabled,
        capabilityChecks: selected,
      });

      if (capabilityNonceRef.current[channel.id] !== nonce) return;

      const capabilityResults = result.capabilityResults || {};
      const hasFailure = Object.values(capabilityResults).some((item) => item?.status === 'failed');
      const hasSkipped = Object.values(capabilityResults).some((item) => item?.status === 'skipped');
      setCapabilityStates((previous) => ({
        ...previous,
        [channel.id]: {
          selected,
          status: hasFailure || hasSkipped || !result.success ? 'error' : 'success',
          text: Object.keys(capabilityResults).length > 0
            ? summarizeCapabilityResults(capabilityResults)
            : result.success
              ? '기능 검사 결과가 반환되지 않았습니다'
              : buildLlmFailureText(result),
          hint: getFirstCapabilityHint(capabilityResults)
            || (!result.success ? buildLlmTestHint(result) : undefined),
          results: capabilityResults,
        },
      }));
    } catch (error: unknown) {
      if (capabilityNonceRef.current[channel.id] !== nonce) return;

      const parsed = getParsedApiError(error);
      setCapabilityStates((previous) => ({
        ...previous,
        [channel.id]: {
          selected,
          status: 'error',
          text: parsed.message || '기능 검사 실패',
          hint: undefined,
          results: {},
        },
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
        className="flex w-full items-center justify-between rounded-[1.35rem] border border-[var(--settings-border)] bg-[var(--settings-surface)] px-5 py-4 text-left shadow-soft-card transition-[background-color,border-color,box-shadow] duration-200 hover:border-[var(--settings-border-strong)] hover:bg-[var(--settings-surface-hover)]"
        onClick={() => setIsCollapsed((previous) => !previous)}
      >
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <h3 className="text-base font-semibold text-foreground">AI 모델 설정</h3>
            <Badge variant="info" className="settings-accent-badge">채널 관리</Badge>
          </div>
          <p className="text-xs text-muted-text">
            제공업체 채널을 추가하면 모델 목록을 자동으로 가져와 복수 선택할 수 있고, 직접 입력도 가능합니다. 설정은 .env 파일에 자동 동기화됩니다.
          </p>
          <p className="mt-1 text-xs text-muted-text">
            API Key는 민감 정보로 마스킹되며, 저장 시 로컬 .env에 기록됩니다. 저장 전 연결 테스트는 .env를 변경하지 않습니다.
          </p>
        </div>
        <span className="text-xs text-muted-text">{isCollapsed ? '▶ 펼치기' : '▼ 접기'}</span>
      </button>

      {!isCollapsed ? (
        <div className="space-y-4 animate-in fade-in slide-in-from-top-2 duration-300">
          <div className="rounded-[1.35rem] border border-[var(--settings-border)] bg-[var(--settings-surface)] p-4 shadow-soft-card">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <h4 className="text-sm font-medium text-foreground">빠른 채널 추가</h4>
                <p className="mt-1 text-xs text-secondary-text">제공업체 프리셋을 먼저 선택한 뒤 설정 초안을 한 번에 만듭니다.</p>
              </div>
              <Badge variant="default" className="border-[var(--settings-border)] bg-[var(--settings-surface-hover)] text-muted-text">{channels.length} 개 채널</Badge>
            </div>
            <div className="flex items-center gap-2">
              <Button type="button" variant="settings-primary" className="whitespace-nowrap" disabled={busy} onClick={addChannel}>
                + 채널 추가
              </Button>
              <Select
                value={addPreset}
                onChange={setAddPreset}
                options={LLM_PROVIDER_TEMPLATES.map((preset) => ({
                  value: preset.channelId,
                  label: preset.label,
                }))}
                disabled={busy}
                placeholder="제공업체 선택"
                className="flex-1"
              />
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between px-1">
              <span className="text-xs font-medium uppercase tracking-wider text-muted-text">채널 목록</span>
              {channels.length > 0 ? (
                <span className="text-[10px] text-muted-text">{channels.filter((c) => c.enabled).length}/{channels.length} 활성화됨</span>
              ) : null}
            </div>

            {channels.length === 0 ? (
              <div className="settings-surface-overlay-muted rounded-[1.35rem] border border-dashed settings-border-strong px-4 py-10 text-center">
                <p className="text-sm font-medium text-secondary-text">아직 채널이 없습니다</p>
                <p className="mt-1 text-xs text-muted-text">제공업체 프리셋을 선택한 뒤 “채널 추가”를 누르면 설정을 시작할 수 있습니다.</p>
                <p className="mt-2 text-xs text-muted-text">
                  연결 테스트는 채널을 추가하고 Base URL, API Key, 모델을 입력한 뒤 사용할 수 있습니다. 테스트만으로는 설정이 저장되지 않습니다.
                </p>
              </div>
            ) : channels.map((channel, index) => (
              <ChannelRow
                key={channel.id}
                channel={channel}
                index={index}
                busy={busy}
                visibleKey={Boolean(visibleKeys[index])}
                expanded={Boolean(expandedRows[index])}
                testState={testStates[index]}
                discoveryState={discoveryStates[channel.id]}
                capabilityState={capabilityStates[channel.id]}
                onUpdate={updateChannel}
                onRemove={removeChannel}
                onToggleExpand={toggleExpand}
                onToggleKeyVisibility={toggleKeyVisibility}
                onTest={(ch, idx) => void handleTest(ch, idx)}
                onDiscoverModels={(channel) => void handleDiscoverModels(channel)}
                onToggleCapability={toggleCapability}
                onCheckCapabilities={(channel) => void handleCapabilityCheck(channel)}
              />
            ))}
          </div>

          {managesRuntimeConfig ? (
            <div className="rounded-[1.35rem] border border-[var(--settings-border)] bg-[var(--settings-surface)] p-4 shadow-soft-card">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <span className="settings-accent-text text-xs font-medium uppercase tracking-wider">런타임 매개변수</span>
                  <p className="mt-1 text-[11px] text-muted-text">기본 모델, 대체 모델, Vision, Temperature가 런타임 설정에 직접 저장됩니다.</p>
                </div>
                <Badge variant="default" className="border-[var(--settings-border)] bg-[var(--settings-surface-hover)] text-muted-text">Runtime</Badge>
              </div>
              <div className="mb-4">
                <HelpLabel
                  label="Temperature"
                  fieldKey="LLM_TEMPERATURE"
                  helpKey="settings.llm_channel.temperature"
                  examples={['LLM_TEMPERATURE=0.2', 'LLM_TEMPERATURE=0.7']}
                  compact
                />
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
                  모델 출력의 무작위성을 조정합니다. 0은 결정적 출력, 2는 최대 무작위성이며 0.7을 권장합니다.
                </p>
              </div>

              {availableModels.length === 0 ? (
                <div className="rounded-xl border border-dashed settings-border-strong settings-surface-overlay-soft px-3 py-2 text-xs text-muted-text">
                  활성 채널을 하나 이상 추가하고 모델을 입력해야 아래의 기본 모델 / 대체 모델 / Vision 옵션이 표시됩니다.
                </div>
              ) : (
                <div className="space-y-4">
                  <div>
                    <HelpLabel
                      htmlFor="runtime-primary-model"
                      label="기본 모델"
                      fieldKey="LITELLM_MODEL"
                      helpKey="settings.llm_channel.primary_model"
                      examples={['LITELLM_MODEL=deepseek/deepseek-v4-flash']}
                      compact
                    />
                    <Select
                      id="runtime-primary-model"
                      value={runtimeConfig.primaryModel}
                      onChange={setPrimaryModel}
                      options={buildModelOptions(availableModels, runtimeConfig.primaryModel, '자동(첫 번째 사용 가능 모델 사용)')}
                      disabled={busy}
                      placeholder=""
                    />
                  </div>

                  <div>
                    <HelpLabel
                      htmlFor="runtime-agent-primary-model"
                      label="Agent 기본 모델"
                      fieldKey="AGENT_LITELLM_MODEL"
                      helpKey="settings.llm_channel.agent_primary_model"
                      examples={['AGENT_LITELLM_MODEL=deepseek/deepseek-v4-pro']}
                      compact
                    />
                    <Select
                      id="runtime-agent-primary-model"
                      value={runtimeConfig.agentPrimaryModel}
                      onChange={(value) => setRuntimeConfig((previous) => ({
                        ...previous,
                        agentPrimaryModel: normalizeAgentPrimaryModel(value),
                      }))}
                      options={buildModelOptions(availableModels, runtimeConfig.agentPrimaryModel, '자동(일반 분석 기본 모델 상속)')}
                      disabled={busy}
                      placeholder=""
                    />
                  </div>

                  <div>
                    <HelpLabel
                      label="대체 모델"
                      fieldKey="LITELLM_FALLBACK_MODELS"
                      helpKey="settings.llm_channel.fallback_models"
                      examples={['LITELLM_FALLBACK_MODELS=deepseek/deepseek-v4-pro,gemini/gemini-3-flash-preview']}
                      compact
                    />
                    <div className="space-y-2 rounded-xl border settings-border-strong settings-surface-overlay-soft p-3">
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
                      대체 모델은 기본 모델이 실패할 때만 사용됩니다. 기본 모델은 대체 모델에 중복 추가되지 않습니다.
                    </p>
                  </div>

                  <div>
                    <HelpLabel
                      htmlFor="runtime-vision-model"
                      label="Vision 모델"
                      fieldKey="VISION_MODEL"
                      helpKey="settings.llm_channel.vision_model"
                      examples={['VISION_MODEL=gemini/gemini-3.1-pro-preview']}
                      compact
                    />
                    <Select
                      id="runtime-vision-model"
                      value={runtimeConfig.visionModel}
                      onChange={(value) => setRuntimeConfig((previous) => ({ ...previous, visionModel: value }))}
                      options={buildModelOptions(availableModels, runtimeConfig.visionModel, '자동(Vision 기본 로직 따름)')}
                      disabled={busy}
                      placeholder=""
                    />
                  </div>
                </div>
              )}
            </div>
          ) : (
            <InlineAlert
              variant="warning"
              message="고급 모델 라우팅 YAML이 설정되어 있습니다. 여기서는 채널 항목과 기본 연결 정보만 관리합니다. 런타임 기본 모델 / 대체 모델 / Vision / Temperature는 아래 공통 필드가 결정합니다. YAML 파싱에 성공하면 YAML의 라우팅과 사용 가능 모델 선언을 기준으로 하며, 이 설정은 YAML 파일 자체를 덮어쓰지 않습니다."
              className="rounded-[1.35rem] px-4 py-3 text-xs shadow-none"
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
              {isSaving ? '저장 중...' : managesRuntimeConfig ? 'AI 설정 저장' : '채널 설정 저장'}
            </Button>
            {!hasChanges ? <span className="text-xs text-muted-text">저장되지 않은 변경 사항이 없습니다</span> : null}
          </div>

          {saveMessage?.type === 'success' ? (
            <InlineAlert
              variant="success"
              message={saveMessage.text}
              className="rounded-lg px-3 py-2 text-sm shadow-none"
            />
          ) : null}

          {saveWarnings.length > 0 ? (
            <InlineAlert
              variant="warning"
              title="저장 후 안내"
              message={(
                <div className="space-y-1">
                  {saveWarnings.map((warning) => (
                    <p key={warning}>{warning}</p>
                  ))}
                </div>
              )}
              className="rounded-lg px-3 py-2 text-sm shadow-none"
            />
          ) : null}

          {saveMessage?.type === 'local-error' ? (
            <InlineAlert
              variant="danger"
              message={saveMessage.text}
              className="rounded-lg px-3 py-2 text-sm shadow-none"
            />
          ) : null}

          {saveMessage?.type === 'error' ? <ApiErrorAlert error={saveMessage.error} /> : null}
        </div>
      ) : null}
    </div>
  );
};
