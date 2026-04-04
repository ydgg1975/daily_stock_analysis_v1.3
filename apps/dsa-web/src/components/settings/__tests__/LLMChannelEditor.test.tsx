import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { LLMChannelEditor } from '../LLMChannelEditor';

vi.mock('../../../api/systemConfig', () => ({
  systemConfigApi: {
    testLLMChannel: vi.fn(),
  },
}));

describe('LLMChannelEditor', () => {
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
        onSaveItems={() => {}}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /OpenAI 官方/i }));

    const input = await screen.findByLabelText('API Key');
    expect(input).toHaveAttribute('type', 'password');

    fireEvent.click(screen.getByRole('button', { name: '显示内容' }));
    expect(input).toHaveAttribute('type', 'text');
  });

  it('shows clear guidance when fallback contains cross-provider model without runtime source', async () => {
    const { container } = render(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'zhipu' },
          { key: 'LLM_ZHIPU_PROTOCOL', value: 'openai' },
          { key: 'LLM_ZHIPU_BASE_URL', value: 'https://open.bigmodel.cn/api/paas/v4' },
          { key: 'LLM_ZHIPU_ENABLED', value: 'true' },
          { key: 'LLM_ZHIPU_API_KEY', value: 'zhipu-secret-key' },
          { key: 'LLM_ZHIPU_MODELS', value: 'glm-4-flash' },
          { key: 'LITELLM_MODEL', value: 'zhipu/glm-4-flash' },
          { key: 'LITELLM_FALLBACK_MODELS', value: 'openai/gpt-4o-free' },
          { key: 'LLM_TEMPERATURE', value: '0.7' },
        ]}
        onSaveItems={() => {}}
      />
    );

    const slider = container.querySelector('input[type="range"]') as HTMLInputElement;
    expect(slider).not.toBeNull();
    fireEvent.change(slider, { target: { value: '0.8' } });
    fireEvent.click(screen.getByRole('button', { name: '保存 AI 配置' }));

    expect(await screen.findByText(/跨 Provider 失败切换请在任务层备用路由中配置/)).toBeInTheDocument();
  });

  it('renders only the selected provider channels in scoped mode', async () => {
    render(
      <LLMChannelEditor
        providerScopeName="zhipu"
        items={[
          { key: 'LLM_CHANNELS', value: 'zhipu,gemini' },
          { key: 'LLM_ZHIPU_PROTOCOL', value: 'openai' },
          { key: 'LLM_ZHIPU_BASE_URL', value: 'https://open.bigmodel.cn/api/paas/v4' },
          { key: 'LLM_ZHIPU_ENABLED', value: 'true' },
          { key: 'LLM_ZHIPU_API_KEY', value: 'zhipu-secret-key' },
          { key: 'LLM_ZHIPU_MODELS', value: 'glm-4-flash' },
          { key: 'LLM_GEMINI_PROTOCOL', value: 'gemini' },
          { key: 'LLM_GEMINI_ENABLED', value: 'true' },
          { key: 'LLM_GEMINI_API_KEY', value: 'gemini-secret-key' },
          { key: 'LLM_GEMINI_MODELS', value: 'gemini-2.5-flash' },
        ]}
        onSaveItems={() => {}}
      />
    );

    expect(screen.getByText('智谱 GLM 高级配置')).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: /智谱 GLM/i }).length).toBeGreaterThan(0);
    expect(screen.queryByRole('button', { name: /Gemini 官方/i })).toBeNull();
    expect(screen.queryByText('运行时参数')).toBeNull();
  });
});
