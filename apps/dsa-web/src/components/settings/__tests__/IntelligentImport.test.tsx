import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { IntelligentImport } from '../IntelligentImport';
import { SystemConfigConflictError } from '../../../api/systemConfig';

const { parseImport, onMergeStockList } = vi.hoisted(() => ({
  parseImport: vi.fn(),
  onMergeStockList: vi.fn(),
}));

vi.mock('../../../api/stocks', () => ({
  stocksApi: {
    parseImport,
    extractFromImage: vi.fn(),
  },
}));

describe('IntelligentImport', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('refreshes config state after a config version conflict', async () => {
    parseImport.mockResolvedValue({
      items: [{ code: 'SZ000001', name: 'Ping An Bank', confidence: 'high' }],
      codes: [],
    });
    onMergeStockList
      .mockRejectedValueOnce(new SystemConfigConflictError('配置版本冲突', 'v2'))
      .mockResolvedValueOnce(undefined);

    render(
      <IntelligentImport
        stockListValue="SH600000"
        onMergeStockList={onMergeStockList}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText('或粘贴 CSV/Excel 复制的文本...'), {
      target: { value: '000001' },
    });
    fireEvent.click(screen.getByRole('button', { name: '解析' }));

    await screen.findByText('SZ000001');

    fireEvent.click(screen.getByRole('button', { name: '合并到自选股' }));

    await waitFor(() => {
      expect(onMergeStockList).toHaveBeenCalledTimes(2);
    });
    expect(onMergeStockList).toHaveBeenCalledWith('SH600000,SZ000001');
    expect(await screen.findByText('配置已更新，请再次点击「合并到自选股」')).toBeInTheDocument();
  });
});
