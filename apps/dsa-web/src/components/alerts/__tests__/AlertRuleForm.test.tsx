import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AlertRuleForm } from '../AlertRuleForm';

const { getAccounts } = vi.hoisted(() => ({
  getAccounts: vi.fn(),
}));

vi.mock('../../../api/portfolio', () => ({
  portfolioApi: {
    getAccounts,
  },
}));

describe('AlertRuleForm', () => {
  const onSubmit = vi.fn();

  beforeEach(() => {
    onSubmit.mockReset();
    onSubmit.mockResolvedValue(undefined);
    getAccounts.mockReset();
    getAccounts.mockResolvedValue({ accounts: [{ id: 9, name: 'Main', market: 'us', baseCurrency: 'USD', isActive: true }] });
  });

  it('submits a price_cross rule payload', async () => {
    render(<AlertRuleForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('규칙 이름'), { target: { value: '茅台가격 돌파' } });
    fireEvent.change(screen.getByLabelText('종목 코드'), { target: { value: '600519' } });
    fireEvent.change(screen.getByLabelText('가격 임계값'), { target: { value: '1800' } });
    fireEvent.click(screen.getByRole('button', { name: '규칙 저장' }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({
        name: '茅台가격 돌파',
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
    fireEvent.click(screen.getByRole('button', { name: '규칙 저장' }));

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
    fireEvent.change(screen.getByLabelText('거래량 급증 배수'), { target: { value: '2.5' } });
    fireEvent.click(screen.getByLabelText('규칙 활성화'));
    fireEvent.click(screen.getByRole('button', { name: '규칙 저장' }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
        target: 'MSFT',
        alertType: 'volume_spike',
        parameters: { multiplier: 2.5 },
        enabled: false,
      }));
    });
  });

  it('submits technical indicator rule payloads', async () => {
    render(<AlertRuleForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('종목 코드'), { target: { value: '600519' } });
    fireEvent.change(screen.getByLabelText('규칙 유형'), { target: { value: 'macd_cross' } });
    fireEvent.change(screen.getByLabelText('교차 방향'), { target: { value: 'bearish_cross' } });
    fireEvent.change(screen.getByLabelText('단기 기간'), { target: { value: '6' } });
    fireEvent.change(screen.getByLabelText('장기 기간'), { target: { value: '13' } });
    fireEvent.change(screen.getByLabelText('시그널 기간'), { target: { value: '5' } });
    fireEvent.click(screen.getByRole('button', { name: '규칙 저장' }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
        target: '600519',
        alertType: 'macd_cross',
        parameters: {
          direction: 'bearish_cross',
          fastPeriod: 6,
          slowPeriod: 13,
          signalPeriod: 5,
        },
      }));
    });
  });

  it('rejects invalid technical indicator boundaries before submit', () => {
    render(<AlertRuleForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('종목 코드'), { target: { value: '600519' } });
    fireEvent.change(screen.getByLabelText('규칙 유형'), { target: { value: 'rsi_threshold' } });
    fireEvent.change(screen.getByLabelText('RSI 임계값'), { target: { value: '200' } });
    fireEvent.click(screen.getByRole('button', { name: '규칙 저장' }));

    expect(screen.getByRole('alert')).toHaveTextContent('RSI 임계값은 0에서 100 사이여야 합니다');
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('rejects indicator period combinations that exceed fetchable history', () => {
    render(<AlertRuleForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('종목 코드'), { target: { value: '600519' } });
    fireEvent.change(screen.getByLabelText('규칙 유형'), { target: { value: 'macd_cross' } });
    fireEvent.change(screen.getByLabelText('단기 기간'), { target: { value: '2' } });
    fireEvent.change(screen.getByLabelText('장기 기간'), { target: { value: '250' } });
    fireEvent.change(screen.getByLabelText('시그널 기간'), { target: { value: '250' } });
    fireEvent.click(screen.getByRole('button', { name: '규칙 저장' }));

    expect(screen.getByRole('alert')).toHaveTextContent('MACD 계산에 필요한 501개 데이터가 최대 365개 제한을 초과합니다.');
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('rejects empty required technical indicator thresholds before submit', () => {
    render(<AlertRuleForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('종목 코드'), { target: { value: '600519' } });
    fireEvent.change(screen.getByLabelText('규칙 유형'), { target: { value: 'rsi_threshold' } });
    fireEvent.click(screen.getByRole('button', { name: '규칙 저장' }));

    expect(screen.getByRole('alert')).toHaveTextContent('RSI 임계값은 비워둘 수 없습니다');
    expect(onSubmit).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText('규칙 유형'), { target: { value: 'cci_threshold' } });
    fireEvent.click(screen.getByRole('button', { name: '규칙 저장' }));

    expect(screen.getByRole('alert')).toHaveTextContent('CCI 임계값은 비워둘 수 없습니다');
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('rejects invalid numeric thresholds before submit', () => {
    render(<AlertRuleForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('종목 코드'), { target: { value: '600519' } });
    fireEvent.change(screen.getByLabelText('가격 임계값'), { target: { value: '0' } });
    fireEvent.click(screen.getByRole('button', { name: '규칙 저장' }));

    expect(screen.getByRole('alert')).toHaveTextContent('가격 임계값은 0보다 큰 숫자여야 합니다');
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('rejects invalid stock code format before submit', () => {
    render(<AlertRuleForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('종목 코드'), { target: { value: 'aapl-2026' } });
    fireEvent.change(screen.getByLabelText('가격 임계값'), { target: { value: '200' } });
    fireEvent.click(screen.getByRole('button', { name: '규칙 저장' }));

    expect(screen.getByRole('alert')).toHaveTextContent('지원하는 종목 형식이 아닙니다. 예: 005930.KS, 091990.KQ, AAPL');
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('filters alert types and submits a watchlist rule payload', async () => {
    render(<AlertRuleForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('대상 범위'), { target: { value: 'watchlist' } });
    expect(screen.queryByText('포트폴리오 손절')).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('가격 임계값'), { target: { value: '10' } });
    fireEvent.click(screen.getByRole('button', { name: '규칙 저장' }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
        targetScope: 'watchlist',
        target: 'default',
        alertType: 'price_cross',
        parameters: { direction: 'above', price: 10 },
      }));
    });
  });

  it('loads accounts and submits portfolio stop-loss mode', async () => {
    render(<AlertRuleForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('대상 범위'), { target: { value: 'portfolio_account' } });
    await waitFor(() => expect(getAccounts).toHaveBeenCalledWith(false));
    expect(screen.queryByText('가격 돌파')).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('계좌'), { target: { value: '9' } });
    fireEvent.change(screen.getByLabelText('손절 모드'), { target: { value: 'breach' } });
    fireEvent.click(screen.getByRole('button', { name: '규칙 저장' }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
        targetScope: 'portfolio_account',
        target: '9',
        alertType: 'portfolio_stop_loss',
        parameters: { mode: 'breach' },
      }));
    });
  });

  it('keeps all account option when account loading fails', async () => {
    getAccounts.mockRejectedValueOnce(new Error('boom'));
    render(<AlertRuleForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('대상 범위'), { target: { value: 'portfolio_holdings' } });
    expect(await screen.findByRole('alert')).toHaveTextContent('boom');
    expect(screen.getByLabelText('계좌')).toHaveValue('all');
  });

  it('keeps form values when submit reports failure', async () => {
    onSubmit.mockResolvedValueOnce(false);
    render(<AlertRuleForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText('종목 코드'), { target: { value: 'aapl' } });
    fireEvent.change(screen.getByLabelText('가격 임계값'), { target: { value: '200' } });
    fireEvent.click(screen.getByRole('button', { name: '규칙 저장' }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    expect(screen.getByLabelText('종목 코드')).toHaveValue('aapl');
    expect(screen.getByLabelText('가격 임계값')).toHaveValue(200);
  });
});
