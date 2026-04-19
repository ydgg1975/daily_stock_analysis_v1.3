import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { LLMChannelEditor } from '../LLMChannelEditor';

const {
  update,
  testLLMChannel,
  discoverLLMChannelModels,
} = vi.hoisted(() => ({
  update: vi.fn(),
  testLLMChannel: vi.fn(),
  discoverLLMChannelModels: vi.fn(),
}));

vi.mock('../../../api/systemConfig', () => ({
  systemConfigApi: {
    update: (...args: unknown[]) => update(...args),
    testLLMChannel: (...args: unknown[]) => testLLMChannel(...args),
    discoverLLMChannelModels: (...args: unknown[]) => discoverLLMChannelModels(...args),
  },
}));

describe('LLMChannelEditor', () => {
  beforeEach(() => {
    update.mockReset();
    testLLMChannel.mockReset();
    discoverLLMChannelModels.mockReset();
  });

  it('renders API Key input with controlled visibility', async () => {
    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'openai' },
          { key: 'LLM_OPENAI_PROTOCOL', value: 'openai' },
          { key: 'LLM_OPENAI_BASE_URL', value: 'https://api.openai.com/v1' },
          { key: 'LLM_OPENAI_ENABLED', value: 'true' },
          { key: 'LLM_OPENAI_API_KEY', value: 'secret-key' },
          { key: 'LLM_OPENAI_MODELS', value: 'gpt-4o-mini' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /OpenAI 官方/i }));

    const input = await screen.findByLabelText('API Key');
    expect(input).toHaveAttribute('type', 'password');

    fireEvent.click(screen.getByRole('button', { name: '显示内容' }));
    expect(input).toHaveAttribute('type', 'text');
  });

  it('hides LiteLLM wording when advanced YAML routing is enabled', () => {
    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'openai' },
          { key: 'LITELLM_CONFIG', value: './litellm_config.yaml' },
          { key: 'LLM_OPENAI_PROTOCOL', value: 'openai' },
          { key: 'LLM_OPENAI_BASE_URL', value: 'https://api.openai.com/v1' },
          { key: 'LLM_OPENAI_ENABLED', value: 'true' },
          { key: 'LLM_OPENAI_API_KEY', value: 'secret-key' },
          { key: 'LLM_OPENAI_MODELS', value: 'gpt-4o-mini' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    expect(screen.getByText(/检测到已配置高级模型路由 YAML/i)).toBeInTheDocument();
    expect(screen.getByText(/运行时主模型 \/ 备选模型 \/ Vision \/ Temperature 仍由下方通用字段决定/i)).toBeInTheDocument();
    expect(screen.queryByText(/LiteLLM/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/LITELLM_CONFIG/i)).not.toBeInTheDocument();
  });

  it('keeps minimax-prefixed models in runtime selections', () => {
    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'openai' },
          { key: 'LLM_OPENAI_PROTOCOL', value: 'openai' },
          { key: 'LLM_OPENAI_BASE_URL', value: 'https://api.example.com/v1' },
          { key: 'LLM_OPENAI_ENABLED', value: 'true' },
          { key: 'LLM_OPENAI_API_KEY', value: 'secret-key' },
          { key: 'LLM_OPENAI_MODELS', value: 'minimax/MiniMax-M1' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    const primaryModelSelect = screen.getByRole('combobox', { name: '主模型' });
    const agentModelSelect = screen.getByRole('combobox', { name: 'Agent 主模型' });
    const visionModelSelect = screen.getByRole('combobox', { name: 'Vision 模型' });

    expect(within(primaryModelSelect).getByRole('option', { name: 'minimax/MiniMax-M1' })).toBeInTheDocument();
    expect(within(agentModelSelect).getByRole('option', { name: 'minimax/MiniMax-M1' })).toBeInTheDocument();
    expect(within(visionModelSelect).getByRole('option', { name: 'minimax/MiniMax-M1' })).toBeInTheDocument();
  });

  it('round-trips a minimax channel: protocol stays minimax and bare model resolves to openai/<id>', async () => {
    update.mockResolvedValue({
      success: true,
      configVersion: 'v2',
      appliedCount: 1,
      skippedMaskedCount: 0,
      reloadTriggered: true,
      updatedKeys: [],
      warnings: [],
    });

    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'minimax' },
          { key: 'LLM_MINIMAX_PROTOCOL', value: 'minimax' },
          { key: 'LLM_MINIMAX_BASE_URL', value: 'https://api.minimax.io/v1' },
          { key: 'LLM_MINIMAX_ENABLED', value: 'true' },
          { key: 'LLM_MINIMAX_API_KEY', value: 'minimax-key' },
          { key: 'LLM_MINIMAX_MODELS', value: 'MiniMax-M1' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />,
    );

    // Bare MiniMax model should be normalized to openai/<id> in runtime selectors,
    // matching backend src/config.py which routes minimax via openai/ prefix.
    const primaryModelSelect = screen.getByRole('combobox', { name: '主模型' });
    expect(within(primaryModelSelect).getByRole('option', { name: 'openai/MiniMax-M1' })).toBeInTheDocument();
    // The minimax/<id> form should NOT appear (it would imply a different runtime route).
    expect(within(primaryModelSelect).queryByRole('option', { name: 'minimax/MiniMax-M1' })).not.toBeInTheDocument();

    // Open the channel row so the model input becomes editable.
    fireEvent.click(screen.getByRole('button', { name: /MiniMax/i }));

    // Trigger save: dirty the model field to enable Save. The save payload assertion below
    // proves the protocol round-trips as 'minimax' (not coerced to 'openai').
    const modelsInput = screen.getByLabelText('模型（逗号分隔）');
    fireEvent.change(modelsInput, { target: { value: 'MiniMax-M1,MiniMax-Text-01' } });
    fireEvent.click(screen.getByRole('button', { name: '保存 AI 配置' }));

    await waitFor(() => {
      expect(update).toHaveBeenCalled();
    });

    const updatePayload = update.mock.calls[0][0];
    expect(updatePayload.items).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ key: 'LLM_MINIMAX_PROTOCOL', value: 'minimax' }),
        expect.objectContaining({ key: 'LLM_MINIMAX_BASE_URL', value: 'https://api.minimax.io/v1' }),
        expect.objectContaining({ key: 'LLM_MINIMAX_MODELS', value: 'MiniMax-M1,MiniMax-Text-01' }),
      ]),
    );
  });

  it('clears stale fallback models when the underlying channel models change', async () => {
    update.mockResolvedValue({
      success: true,
      configVersion: 'v2',
      appliedCount: 1,
      skippedMaskedCount: 0,
      reloadTriggered: true,
      updatedKeys: [],
      warnings: [],
    });

    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'openai' },
          { key: 'LLM_OPENAI_PROTOCOL', value: 'openai' },
          { key: 'LLM_OPENAI_BASE_URL', value: 'https://api.openai.com/v1' },
          { key: 'LLM_OPENAI_ENABLED', value: 'true' },
          { key: 'LLM_OPENAI_API_KEY', value: 'sk-test' },
          { key: 'LLM_OPENAI_MODELS', value: 'gpt-4o-mini,gpt-4o' },
          { key: 'LITELLM_MODEL', value: 'openai/gpt-4o-mini' },
          { key: 'LITELLM_FALLBACK_MODELS', value: 'openai/gpt-4o' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />,
    );

    // Initially the fallback (openai/gpt-4o) should be checked.
    const fallbackBefore = screen.getByRole('checkbox', { name: 'openai/gpt-4o' }) as HTMLInputElement;
    expect(fallbackBefore.checked).toBe(true);

    // User removes gpt-4o from the channel's model list — leaves only gpt-4o-mini.
    fireEvent.click(screen.getByRole('button', { name: /OpenAI 官方/i }));
    const modelsInput = screen.getByLabelText('模型（逗号分隔）');
    fireEvent.change(modelsInput, { target: { value: 'gpt-4o-mini' } });

    // The stale fallback option should disappear from the available list and not block save.
    await waitFor(() => {
      expect(screen.queryByRole('checkbox', { name: 'openai/gpt-4o' })).not.toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: '保存 AI 配置' }));
    await waitFor(() => {
      expect(update).toHaveBeenCalled();
    });

    const updatePayload = update.mock.calls[0][0];
    // Stale fallback should have been cleared from runtime config.
    expect(updatePayload.items).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ key: 'LITELLM_FALLBACK_MODELS', value: '' }),
      ]),
    );
  });

  it('checks protocol-prefixed selected model when discovery returns bare id', async () => {
    discoverLLMChannelModels.mockResolvedValue({
      success: true,
      message: 'LLM channel model discovery succeeded',
      error: null,
      resolvedProtocol: 'openai',
      models: ['MiniMax-M1'],
      latencyMs: 80,
    });

    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'dashscope' },
          { key: 'LLM_DASHSCOPE_PROTOCOL', value: 'openai' },
          { key: 'LLM_DASHSCOPE_BASE_URL', value: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
          { key: 'LLM_DASHSCOPE_ENABLED', value: 'true' },
          { key: 'LLM_DASHSCOPE_API_KEY', value: 'sk-test' },
          { key: 'LLM_DASHSCOPE_MODELS', value: 'openai/MiniMax-M1' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /通义千问/i }));
    fireEvent.click(screen.getByRole('button', { name: '获取模型' }));

    const checkbox = await screen.findByLabelText('MiniMax-M1');
    expect(checkbox).toBeChecked();

    fireEvent.click(checkbox);
    await waitFor(() => {
      expect(screen.getByLabelText('手动模型（逗号分隔）')).toHaveValue('');
    });
  });

  it('does not treat unknown-prefixed selected model as equivalent to bare discovered id', async () => {
    discoverLLMChannelModels.mockResolvedValue({
      success: true,
      message: 'LLM channel model discovery succeeded',
      error: null,
      resolvedProtocol: 'openai',
      models: ['MiniMax-M1'],
      latencyMs: 80,
    });

    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'dashscope' },
          { key: 'LLM_DASHSCOPE_PROTOCOL', value: 'openai' },
          { key: 'LLM_DASHSCOPE_BASE_URL', value: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
          { key: 'LLM_DASHSCOPE_ENABLED', value: 'true' },
          { key: 'LLM_DASHSCOPE_API_KEY', value: 'sk-test' },
          { key: 'LLM_DASHSCOPE_MODELS', value: 'minimax/MiniMax-M1' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /通义千问/i }));
    fireEvent.click(screen.getByRole('button', { name: '获取模型' }));

    const checkbox = await screen.findByLabelText('MiniMax-M1');
    expect(checkbox).not.toBeChecked();
    expect(screen.getByLabelText('手动模型（逗号分隔）')).toHaveValue('minimax/MiniMax-M1');
  });

  it('discovers models and writes selected values back to channel config', async () => {
    discoverLLMChannelModels.mockResolvedValue({
      success: true,
      message: 'LLM channel model discovery succeeded',
      error: null,
      resolvedProtocol: 'openai',
      models: ['qwen-plus', 'qwen-turbo'],
      latencyMs: 88,
    });
    update.mockResolvedValue({
      success: true,
      configVersion: 'v2',
      appliedCount: 1,
      skippedMaskedCount: 0,
      reloadTriggered: true,
      updatedKeys: ['LLM_DASHSCOPE_MODELS'],
      warnings: [],
    });

    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'dashscope' },
          { key: 'LLM_DASHSCOPE_PROTOCOL', value: 'openai' },
          { key: 'LLM_DASHSCOPE_BASE_URL', value: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
          { key: 'LLM_DASHSCOPE_ENABLED', value: 'true' },
          { key: 'LLM_DASHSCOPE_API_KEY', value: 'sk-test' },
          { key: 'LLM_DASHSCOPE_MODELS', value: 'qwen-old' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /Dashscope/i }));
    fireEvent.click(screen.getByRole('button', { name: '获取模型' }));

    const qwenPlusCheckbox = await screen.findByLabelText('qwen-plus');
    fireEvent.click(qwenPlusCheckbox);

    await waitFor(() => {
      expect(screen.getByLabelText('手动模型（逗号分隔）')).toHaveValue('qwen-old,qwen-plus');
    });

    expect(discoverLLMChannelModels).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'dashscope',
        protocol: 'openai',
        baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        apiKey: 'sk-test',
        models: ['qwen-old'],
      }),
    );

    fireEvent.click(screen.getByRole('button', { name: '保存 AI 配置' }));

    await waitFor(() => {
      expect(update).toHaveBeenCalled();
    });

    const updatePayload = update.mock.calls[0][0];
    expect(updatePayload.items).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ key: 'LLM_DASHSCOPE_MODELS', value: 'qwen-old,qwen-plus' }),
      ]),
    );
  });

  it('keeps manual model input available when discovery fails', async () => {
    discoverLLMChannelModels.mockResolvedValue({
      success: false,
      message: 'Model discovery is not supported for this protocol',
      error: 'LLM channel does not support /models discovery yet',
      resolvedProtocol: 'gemini',
      models: [],
      latencyMs: null,
    });

    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'gemini' },
          { key: 'LLM_GEMINI_PROTOCOL', value: 'gemini' },
          { key: 'LLM_GEMINI_BASE_URL', value: '' },
          { key: 'LLM_GEMINI_ENABLED', value: 'true' },
          { key: 'LLM_GEMINI_API_KEY', value: 'sk-test' },
          { key: 'LLM_GEMINI_MODELS', value: '' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /Gemini 官方/i }));
    fireEvent.click(screen.getByRole('button', { name: '获取模型' }));

    await screen.findByText('LLM channel does not support /models discovery yet');

    const manualInput = screen.getByLabelText('模型（逗号分隔）');
    fireEvent.change(manualInput, { target: { value: 'gemini-2.5-flash' } });
    expect(manualInput).toHaveValue('gemini-2.5-flash');
  });

  it('does not apply stale discovery response after channel list re-sync', async () => {
    let resolvePendingFirst!: (value: unknown) => void;
    const pendingFirst = new Promise((resolve) => {
      resolvePendingFirst = resolve;
    });

    discoverLLMChannelModels
      .mockImplementationOnce(() => pendingFirst)
      .mockResolvedValueOnce({
        success: true,
        message: 'LLM channel model discovery succeeded',
        error: null,
        resolvedProtocol: 'openai',
        models: ['dashscope-plus'],
        latencyMs: 30,
      });

    const renderResult = render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'openai' },
          { key: 'LLM_OPENAI_PROTOCOL', value: 'openai' },
          { key: 'LLM_OPENAI_BASE_URL', value: 'https://api.openai.com/v1' },
          { key: 'LLM_OPENAI_ENABLED', value: 'true' },
          { key: 'LLM_OPENAI_API_KEY', value: 'open-key' },
          { key: 'LLM_OPENAI_MODELS', value: 'gpt-old' },
          { key: 'LLM_DASHSCOPE_PROTOCOL', value: 'openai' },
          { key: 'LLM_DASHSCOPE_BASE_URL', value: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
          { key: 'LLM_DASHSCOPE_ENABLED', value: 'true' },
          { key: 'LLM_DASHSCOPE_API_KEY', value: 'dash-key' },
          { key: 'LLM_DASHSCOPE_MODELS', value: 'dash-old' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /OpenAI 官方/i }));
    fireEvent.click(screen.getByRole('button', { name: '获取模型' }));

    renderResult.rerender(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'dashscope' },
          { key: 'LLM_DASHSCOPE_PROTOCOL', value: 'openai' },
          { key: 'LLM_DASHSCOPE_BASE_URL', value: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
          { key: 'LLM_DASHSCOPE_ENABLED', value: 'true' },
          { key: 'LLM_DASHSCOPE_API_KEY', value: 'dash-key' },
          { key: 'LLM_DASHSCOPE_MODELS', value: 'dash-old' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /通义千问/i }));
    fireEvent.click(screen.getByRole('button', { name: '获取模型' }));

    const dashModelCheckbox = await screen.findByLabelText('dashscope-plus');
    fireEvent.click(dashModelCheckbox);

    expect(screen.getByLabelText('手动模型（逗号分隔）')).toHaveValue('dash-old,dashscope-plus');

    resolvePendingFirst({
      success: true,
      message: 'LLM channel model discovery succeeded',
      error: null,
      resolvedProtocol: 'openai',
      models: ['stale-openai'],
      latencyMs: 20,
    });

    await waitFor(() => {
      expect(screen.getByLabelText('手动模型（逗号分隔）')).toHaveValue('dash-old,dashscope-plus');
    });
    expect(screen.queryByLabelText('stale-openai')).not.toBeInTheDocument();
  });

  it('does not apply stale discovery response after inline channel edit', async () => {
    let resolvePendingFirst!: (value: unknown) => void;
    const pendingFirst = new Promise((resolve) => {
      resolvePendingFirst = resolve;
    });

    discoverLLMChannelModels.mockImplementationOnce(() => pendingFirst);

    render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'dashscope' },
          { key: 'LLM_DASHSCOPE_PROTOCOL', value: 'openai' },
          { key: 'LLM_DASHSCOPE_BASE_URL', value: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
          { key: 'LLM_DASHSCOPE_ENABLED', value: 'true' },
          { key: 'LLM_DASHSCOPE_API_KEY', value: 'dash-key' },
          { key: 'LLM_DASHSCOPE_MODELS', value: 'qwen-old' },
        ]}
        configVersion="v1"
        maskToken="******"
        onSaved={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /Dashscope/i }));
    fireEvent.click(screen.getByRole('button', { name: '获取模型' }));

    const baseUrlInput = screen.getByLabelText('Base URL');
    fireEvent.change(baseUrlInput, {
      target: { value: 'https://dashscope.aliyuncs.com/compatible-mode/v2' },
    });

    resolvePendingFirst({
      success: true,
      message: 'LLM channel model discovery succeeded',
      error: null,
      resolvedProtocol: 'openai',
      models: ['stale-openai'],
      latencyMs: 20,
    });

    await waitFor(() => {
      expect(screen.getByLabelText('模型（逗号分隔）')).toHaveValue('qwen-old');
      expect(screen.queryByLabelText('stale-openai')).not.toBeInTheDocument();
    });
  });
});
