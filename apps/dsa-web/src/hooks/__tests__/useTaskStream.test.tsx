import { renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useTaskStream } from '../useTaskStream';

const { getTaskStreamUrl } = vi.hoisted(() => ({
  getTaskStreamUrl: vi.fn(() => 'http://localhost/api/v1/analysis/tasks/stream'),
}));

vi.mock('../../api/analysis', () => ({
  analysisApi: {
    getTaskStreamUrl,
  },
}));

type MockEventSourceInstance = {
  addEventListener: ReturnType<typeof vi.fn>;
  close: ReturnType<typeof vi.fn>;
  onerror: ((event: Event) => void) | null;
  listeners: Map<string, EventListener>;
};

describe('useTaskStream', () => {
  let eventSourceInstance: MockEventSourceInstance;

  beforeEach(() => {
    vi.clearAllMocks();

    eventSourceInstance = {
      addEventListener: vi.fn(),
      close: vi.fn(),
      onerror: null,
      listeners: new Map(),
    };

    class MockEventSource {
      addEventListener = eventSourceInstance.addEventListener;
      close = eventSourceInstance.close;
      onerror = eventSourceInstance.onerror;

      constructor(...args: unknown[]) {
        void args;
      }
    }

    Object.defineProperty(window, 'EventSource', {
      writable: true,
      configurable: true,
      value: MockEventSource,
    });

    eventSourceInstance.addEventListener.mockImplementation((type: string, listener: EventListener) => {
      eventSourceInstance.listeners.set(type, listener);
    });
  });

  it('closes the SSE connection when the hook unmounts', () => {
    const { unmount } = renderHook(() => useTaskStream({ enabled: true }));

    expect(getTaskStreamUrl).toHaveBeenCalledTimes(1);

    unmount();

    expect(eventSourceInstance.close).toHaveBeenCalled();
  });

  it('registers and forwards task_updated events', () => {
    const onTaskUpdated = vi.fn();

    renderHook(() => useTaskStream({ enabled: true, onTaskUpdated }));

    expect(eventSourceInstance.addEventListener).toHaveBeenCalledWith(
      'task_updated',
      expect.any(Function),
    );

    const listener = eventSourceInstance.listeners.get('task_updated');
    expect(listener).toBeTypeOf('function');

    listener?.({
      data: JSON.stringify({
        task_id: 'task-1',
        stock_code: '600519',
        status: 'processing',
        progress: 46,
        message: '正在分析信号',
        report_type: 'detailed',
        created_at: '2026-04-07T12:00:00Z',
      }),
    } as MessageEvent);

    expect(onTaskUpdated).toHaveBeenCalledWith(
      expect.objectContaining({
        taskId: 'task-1',
        stockCode: '600519',
        status: 'processing',
        progress: 46,
      }),
    );
  });
});
