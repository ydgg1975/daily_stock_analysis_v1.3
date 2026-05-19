import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AlertRuleForm } from '../AlertRuleForm';

describe('AlertRuleForm', () => {
  const onSubmit = vi.fn();

  beforeEach(() => {
    onSubmit.mockReset();
    onSubmit.mockResolvedValue(undefined);
  });

  it('submits a price_cross rule payload', async () => {
    render(<AlertRuleForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('규칙 이름'), { target: { value: '마오타이 가격 돌파' } });
    fireEvent.change(screen.getByLabelText('종목 코드'), { target: { value: '600519' } });
    fireEvent.change(screen.getByLabelText('가격 임계값'), { target: { value: '1800' } });
    fireEvent.click(screen.getByRole('button', { name: '규칙 만들기' }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({
        name: '마오타이 가격 돌파',
        targetScope: 'single_symbol',
        target: '600519',
        alertType: 'price_cross',
        parameters: { direction: 'above', price: 1800 },
        severity: 'warning',
        enabled: true,
      });
    });
  });

  it('submits a price_change_percent rule payload', async () => {
    render(<AlertRuleForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('종목 코드'), { target: { value: 'aapl' } });
    fireEvent.change(screen.getByLabelText('규칙 유형'), { target: { value: 'price_change_percent' } });
    fireEvent.change(screen.getByLabelText('방향'), { target: { value: 'down' } });
    fireEvent.change(screen.getByLabelText('등락률 임계값(%)'), { target: { value: '3.5' } });
    fireEvent.change(screen.getByLabelText('심각도'), { target: { value: 'critical' } });
    fireEvent.click(screen.getByRole('button', { name: '규칙 만들기' }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
        target: 'AAPL',
        alertType: 'price_change_percent',
        parameters: { direction: 'down', changePct: 3.5 },
        severity: 'critical',
      }));
    });
  });

  it('submits a volume_spike rule payload and supports disabled creation', async () => {
    render(<AlertRuleForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('종목 코드'), { target: { value: 'msft' } });
    fireEvent.change(screen.getByLabelText('규칙 유형'), { target: { value: 'volume_spike' } });
    fireEvent.change(screen.getByLabelText('거래량 배수'), { target: { value: '2.5' } });
    fireEvent.click(screen.getByLabelText('생성 후 바로 활성화'));
    fireEvent.click(screen.getByRole('button', { name: '규칙 만들기' }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
        target: 'MSFT',
        alertType: 'volume_spike',
        parameters: { multiplier: 2.5 },
        enabled: false,
      }));
    });
  });

  it('rejects invalid numeric thresholds before submit', () => {
    render(<AlertRuleForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('종목 코드'), { target: { value: '600519' } });
    fireEvent.change(screen.getByLabelText('가격 임계값'), { target: { value: '0' } });
    fireEvent.click(screen.getByRole('button', { name: '규칙 만들기' }));

    expect(screen.getByRole('alert')).toHaveTextContent('가격 임계값은 0보다 큰 숫자여야 합니다.');
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('rejects invalid stock code format before submit', () => {
    render(<AlertRuleForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('종목 코드'), { target: { value: 'aapl-2026' } });
    fireEvent.change(screen.getByLabelText('가격 임계값'), { target: { value: '200' } });
    fireEvent.click(screen.getByRole('button', { name: '규칙 만들기' }));

    expect(screen.getByRole('alert')).toHaveTextContent('종목 코드 형식이 올바르지 않습니다');
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('keeps form values when submit reports failure', async () => {
    onSubmit.mockResolvedValueOnce(false);
    render(<AlertRuleForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('종목 코드'), { target: { value: 'aapl' } });
    fireEvent.change(screen.getByLabelText('가격 임계값'), { target: { value: '200' } });
    fireEvent.click(screen.getByRole('button', { name: '규칙 만들기' }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    expect(screen.getByLabelText('종목 코드')).toHaveValue('aapl');
    expect(screen.getByLabelText('가격 임계값')).toHaveValue(200);
  });
});

