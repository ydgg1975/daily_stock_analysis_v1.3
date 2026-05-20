import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { IntelligentImport } from '../IntelligentImport';
import { SystemConfigConflictError } from '../../../api/systemConfig';

const { parseImport, update, onMerged } = vi.hoisted(() => ({
  parseImport: vi.fn(),
  update: vi.fn(),
  onMerged: vi.fn(),
}));

vi.mock('../../../api/stocks', () => ({
  stocksApi: {
    parseImport,
    extractFromImage: vi.fn(),
  },
}));

vi.mock('../../../api/systemConfig', async () => {
  const actual = await vi.importActual<typeof import('../../../api/systemConfig')>('../../../api/systemConfig');
  return {
    ...actual,
    systemConfigApi: {
      ...actual.systemConfigApi,
      update,
    },
  };
});

describe('IntelligentImport', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('opens the matching hidden file input when the picker buttons are clicked', () => {
    const { container } = render(
      <IntelligentImport
        stockListValue="SH600000"
        configVersion="v1"
        maskToken="******"
        onMerged={onMerged}
      />,
    );

    const inputs = container.querySelectorAll('input[type="file"]');
    expect(inputs).toHaveLength(2);

    const imageClick = vi.fn();
    const dataClick = vi.fn();

    Object.defineProperty(inputs[0], 'click', {
      value: imageClick,
      configurable: true,
    });
    Object.defineProperty(inputs[1], 'click', {
      value: dataClick,
      configurable: true,
    });

    fireEvent.click(screen.getByRole('button', { name: '이미지 선택' }));
    fireEvent.click(screen.getByRole('button', { name: '파일 선택' }));

    expect(imageClick).toHaveBeenCalledTimes(1);
    expect(dataClick).toHaveBeenCalledTimes(1);
  });

  it('does not open hidden file inputs when the import actions are disabled', () => {
    const { container } = render(
      <IntelligentImport
        stockListValue="SH600000"
        configVersion="v1"
        maskToken="******"
        onMerged={onMerged}
        disabled
      />,
    );

    const inputs = container.querySelectorAll('input[type="file"]');
    expect(inputs).toHaveLength(2);

    const imageClick = vi.fn();
    const dataClick = vi.fn();

    Object.defineProperty(inputs[0], 'click', {
      value: imageClick,
      configurable: true,
    });
    Object.defineProperty(inputs[1], 'click', {
      value: dataClick,
      configurable: true,
    });

    fireEvent.click(screen.getByRole('button', { name: '이미지 선택' }));
    fireEvent.click(screen.getByRole('button', { name: '파일 선택' }));

    expect(imageClick).not.toHaveBeenCalled();
    expect(dataClick).not.toHaveBeenCalled();
  });

  it('refreshes config state after a config version conflict', async () => {
    parseImport.mockResolvedValue({
      items: [{ code: 'SZ000001', name: 'Ping An Bank', confidence: 'high' }],
      codes: [],
    });
    update.mockRejectedValue(
      new SystemConfigConflictError('설정 버전 충돌', 'v2'),
    );

    render(
      <IntelligentImport
        stockListValue="SH600000"
        configVersion="v1"
        maskToken="******"
        onMerged={onMerged}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText('또는 CSV/Excel에서 복사한 텍스트를 붙여넣기...'), {
      target: { value: '000001' },
    });
    fireEvent.click(screen.getByRole('button', { name: '파싱' }));

    await screen.findByText('SZ000001');

    fireEvent.click(screen.getByRole('button', { name: '관심 종목에 병합' }));

    await waitFor(() => {
      expect(update).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(onMerged).toHaveBeenCalledWith('SH600000,SZ000001');
    });
    expect(await screen.findByText('설정이 업데이트되었습니다. 관심 종목에 병합을 다시 누르세요')).toBeInTheDocument();
  });
});
