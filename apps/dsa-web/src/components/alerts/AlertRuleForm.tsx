import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { portfolioApi } from '../../api/portfolio';
import type {
  AlertRuleCreateRequest,
  AlertSeverity,
  AlertTargetScope,
  AlertType,
  PortfolioStopLossMode,
} from '../../types/alerts';
import type { PortfolioAccountItem } from '../../types/portfolio';
import { validateStockCode } from '../../utils/validation';
import { Button, Card, Checkbox, Input, Select } from '../common';

const SYMBOL_ALERT_TYPE_OPTIONS = [
  { value: 'price_cross', label: '가격 돌파' },
  { value: 'price_change_percent', label: '등락률' },
  { value: 'volume_spike', label: '거래량 급증' },
  { value: 'ma_price_cross', label: '이동평균 교차' },
  { value: 'rsi_threshold', label: 'RSI 임계값' },
  { value: 'macd_cross', label: 'MACD 교차' },
  { value: 'kdj_cross', label: 'KDJ 교차' },
  { value: 'cci_threshold', label: 'CCI 임계값' },
];

const PORTFOLIO_ALERT_TYPE_OPTIONS = [
  { value: 'portfolio_stop_loss', label: '포트폴리오 손절' },
  { value: 'portfolio_concentration', label: '포트폴리오 집중도' },
  { value: 'portfolio_drawdown', label: '포트폴리오 낙폭' },
  { value: 'portfolio_price_stale', label: '포트폴리오 가격 지연' },
];

const TARGET_SCOPE_OPTIONS = [
  { value: 'single_symbol', label: '단일 종목' },
  { value: 'watchlist', label: '관심 목록' },
  { value: 'portfolio_holdings', label: '포트폴리오 보유 종목' },
  { value: 'portfolio_account', label: '포트폴리오 계좌' },
];

const SEVERITY_OPTIONS = [
  { value: 'info', label: '정보' },
  { value: 'warning', label: '경고' },
  { value: 'critical', label: '긴급' },
];

const PRICE_DIRECTION_OPTIONS = [
  { value: 'above', label: '상향 돌파' },
  { value: 'below', label: '하향 돌파' },
];

const CHANGE_DIRECTION_OPTIONS = [
  { value: 'up', label: '상승률 초과' },
  { value: 'down', label: '하락률 초과' },
];

const THRESHOLD_DIRECTION_OPTIONS = [
  { value: 'above', label: '이상' },
  { value: 'below', label: '이하' },
];

const CROSS_DIRECTION_OPTIONS = [
  { value: 'bullish_cross', label: '골든크로스' },
  { value: 'bearish_cross', label: '데드크로스' },
];

const STOP_LOSS_MODE_OPTIONS = [
  { value: 'near', label: '손절가 근접' },
  { value: 'breach', label: '손절가 이탈' },
];

const MAX_REQUESTED_DAYS = 365;

interface AlertRuleFormProps {
  onSubmit: (payload: AlertRuleCreateRequest) => Promise<boolean | void> | boolean | void;
  isSubmitting?: boolean;
}

function isPortfolioScope(scope: AlertTargetScope): boolean {
  return scope === 'portfolio_holdings' || scope === 'portfolio_account';
}

function defaultAlertTypeForScope(scope: AlertTargetScope): AlertType {
  return isPortfolioScope(scope) ? 'portfolio_stop_loss' : 'price_cross';
}

function optionsForScope(scope: AlertTargetScope) {
  return isPortfolioScope(scope) ? PORTFOLIO_ALERT_TYPE_OPTIONS : SYMBOL_ALERT_TYPE_OPTIONS;
}

export const AlertRuleForm: React.FC<AlertRuleFormProps> = ({ onSubmit, isSubmitting = false }) => {
  const [name, setName] = useState('');
  const [targetScope, setTargetScope] = useState<AlertTargetScope>('single_symbol');
  const [target, setTarget] = useState('');
  const [portfolioTarget, setPortfolioTarget] = useState('all');
  const [accounts, setAccounts] = useState<PortfolioAccountItem[]>([]);
  const [accountsError, setAccountsError] = useState<string | null>(null);
  const [alertType, setAlertType] = useState<AlertType>('price_cross');
  const [severity, setSeverity] = useState<AlertSeverity>('warning');
  const [enabled, setEnabled] = useState(true);
  const [priceDirection, setPriceDirection] = useState<'above' | 'below'>('above');
  const [changeDirection, setChangeDirection] = useState<'up' | 'down'>('up');
  const [thresholdDirection, setThresholdDirection] = useState<'above' | 'below'>('above');
  const [crossDirection, setCrossDirection] = useState<'bullish_cross' | 'bearish_cross'>('bullish_cross');
  const [stopLossMode, setStopLossMode] = useState<PortfolioStopLossMode>('near');
  const [price, setPrice] = useState('');
  const [changePct, setChangePct] = useState('');
  const [multiplier, setMultiplier] = useState('');
  const [window, setWindow] = useState('20');
  const [period, setPeriod] = useState('12');
  const [threshold, setThreshold] = useState('');
  const [fastPeriod, setFastPeriod] = useState('12');
  const [slowPeriod, setSlowPeriod] = useState('26');
  const [signalPeriod, setSignalPeriod] = useState('9');
  const [kPeriod, setKPeriod] = useState('3');
  const [dPeriod, setDPeriod] = useState('3');
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (!isPortfolioScope(targetScope)) return undefined;
    let cancelled = false;
    void portfolioApi.getAccounts(false)
      .then((response) => {
        if (cancelled) return;
        setAccounts(response.accounts ?? []);
        setAccountsError(null);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setAccounts([]);
        setAccountsError(error instanceof Error ? error.message : '계좌 목록을 불러오지 못했습니다.');
      });
    return () => {
      cancelled = true;
    };
  }, [targetScope]);

  const alertTypeOptions = useMemo(() => optionsForScope(targetScope), [targetScope]);
  const portfolioTargetOptions = useMemo(() => [
    { value: 'all', label: '전체 계좌' },
    ...accounts.map((account) => ({ value: String(account.id), label: `${account.name} #${account.id}` })),
  ], [accounts]);

  const resetParameters = (nextType: AlertType) => {
    if (nextType === 'price_cross') {
      setPriceDirection('above');
      setPrice('');
    } else if (nextType === 'price_change_percent') {
      setChangeDirection('up');
      setChangePct('');
    } else if (nextType === 'volume_spike') {
      setMultiplier('');
    } else if (nextType === 'ma_price_cross') {
      setThresholdDirection('above');
      setWindow('20');
    } else if (nextType === 'rsi_threshold') {
      setThresholdDirection('above');
      setPeriod('12');
      setThreshold('');
    } else if (nextType === 'macd_cross') {
      setCrossDirection('bullish_cross');
      setFastPeriod('12');
      setSlowPeriod('26');
      setSignalPeriod('9');
    } else if (nextType === 'kdj_cross') {
      setCrossDirection('bullish_cross');
      setPeriod('9');
      setKPeriod('3');
      setDPeriod('3');
    } else if (nextType === 'cci_threshold') {
      setThresholdDirection('above');
      setPeriod('14');
      setThreshold('');
    } else if (nextType === 'portfolio_stop_loss') {
      setStopLossMode('near');
    }
  };

  const parsePositiveNumber = (value: string, label: string): number | null => {
    const parsed = Number(value);
    if (!Number.isFinite(parsed) || parsed <= 0) {
      setFormError(`${label}은 0보다 큰 숫자여야 합니다.`);
      return null;
    }
    return parsed;
  };

  const parseIntegerInRange = (value: string, label: string, min = 2, max = 250): number | null => {
    const parsed = Number(value);
    if (!Number.isInteger(parsed) || parsed < min || parsed > max) {
      setFormError(`${label}은 ${min}에서 ${max} 사이의 정수여야 합니다.`);
      return null;
    }
    return parsed;
  };

  const parseFiniteNumber = (value: string, label: string): number | null => {
    if (value.trim() === '') {
      setFormError(`${label}은 비워둘 수 없습니다.`);
      return null;
    }
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) {
      setFormError(`${label}은 유효한 숫자여야 합니다.`);
      return null;
    }
    return parsed;
  };

  const ensureRequiredBarsWithinLimit = (label: string, requiredBars: number): boolean => {
    if (requiredBars > MAX_REQUESTED_DAYS) {
      setFormError(`${label} 계산에 필요한 ${requiredBars}개 데이터가 최대 ${MAX_REQUESTED_DAYS}개 제한을 초과합니다.`);
      return false;
    }
    return true;
  };

  const buildParameters = (): AlertRuleCreateRequest['parameters'] | null => {
    if (alertType === 'price_cross') {
      const parsedPrice = parsePositiveNumber(price, '가격 임계값');
      return parsedPrice == null ? null : { direction: priceDirection, price: parsedPrice };
    }
    if (alertType === 'price_change_percent') {
      const parsedChangePct = parsePositiveNumber(changePct, '등락률 임계값');
      return parsedChangePct == null ? null : { direction: changeDirection, changePct: parsedChangePct };
    }
    if (alertType === 'volume_spike') {
      const parsedMultiplier = parsePositiveNumber(multiplier, '거래량 배수');
      return parsedMultiplier == null ? null : { multiplier: parsedMultiplier };
    }
    if (alertType === 'ma_price_cross') {
      const parsedWindow = parseIntegerInRange(window, '이동평균 기간');
      return parsedWindow == null ? null : { direction: thresholdDirection, window: parsedWindow };
    }
    if (alertType === 'rsi_threshold') {
      const parsedPeriod = parseIntegerInRange(period, 'RSI 기간');
      const parsedThreshold = parseFiniteNumber(threshold, 'RSI 임계값');
      if (parsedPeriod == null || parsedThreshold == null) return null;
      if (parsedThreshold < 0 || parsedThreshold > 100) {
        setFormError('RSI 임계값은 0에서 100 사이여야 합니다.');
        return null;
      }
      return { direction: thresholdDirection, period: parsedPeriod, threshold: parsedThreshold };
    }
    if (alertType === 'macd_cross') {
      const parsedFast = parseIntegerInRange(fastPeriod, '단기 기간');
      const parsedSlow = parseIntegerInRange(slowPeriod, '장기 기간');
      const parsedSignal = parseIntegerInRange(signalPeriod, '시그널 기간');
      if (parsedFast == null || parsedSlow == null || parsedSignal == null) return null;
      if (parsedFast >= parsedSlow) {
        setFormError('단기 기간은 장기 기간보다 작아야 합니다.');
        return null;
      }
      if (!ensureRequiredBarsWithinLimit('MACD', parsedSlow + parsedSignal + 1)) return null;
      return { direction: crossDirection, fastPeriod: parsedFast, slowPeriod: parsedSlow, signalPeriod: parsedSignal };
    }
    if (alertType === 'kdj_cross') {
      const parsedPeriod = parseIntegerInRange(period, 'KDJ 기간');
      const parsedK = parseIntegerInRange(kPeriod, 'K 평활 기간');
      const parsedD = parseIntegerInRange(dPeriod, 'D 평활 기간');
      if (parsedPeriod == null || parsedK == null || parsedD == null) return null;
      if (!ensureRequiredBarsWithinLimit('KDJ', parsedPeriod + parsedK + parsedD + 1)) return null;
      return { direction: crossDirection, period: parsedPeriod, kPeriod: parsedK, dPeriod: parsedD };
    }
    if (alertType === 'cci_threshold') {
      const parsedPeriod = parseIntegerInRange(period, 'CCI 기간');
      const parsedThreshold = parseFiniteNumber(threshold, 'CCI 임계값');
      return parsedPeriod == null || parsedThreshold == null ? null : { direction: thresholdDirection, period: parsedPeriod, threshold: parsedThreshold };
    }
    if (alertType === 'portfolio_stop_loss') {
      return { mode: stopLossMode };
    }
    return {};
  };

  const handleScopeChange = (value: string) => {
    const nextScope = value as AlertTargetScope;
    const nextType = defaultAlertTypeForScope(nextScope);
    setTargetScope(nextScope);
    setAlertType(nextType);
    setPortfolioTarget('all');
    resetParameters(nextType);
    setFormError(null);
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    let resolvedTarget = target.trim();
    if (targetScope === 'single_symbol') {
      const targetValidation = validateStockCode(target);
      if (!targetValidation.valid) {
        setFormError(targetValidation.message ?? '종목 코드 형식이 올바르지 않습니다.');
        return;
      }
      resolvedTarget = targetValidation.normalized;
    } else if (targetScope === 'watchlist') {
      resolvedTarget = 'default';
    } else {
      resolvedTarget = portfolioTarget;
    }

    const parameters = buildParameters();
    if (parameters == null) return;

    setFormError(null);
    const submitted = await onSubmit({
      name: name.trim() || undefined,
      targetScope,
      target: resolvedTarget,
      alertType,
      parameters,
      severity,
      enabled,
    });
    if (submitted === false) return;
    setName('');
    setTarget('');
    setPortfolioTarget('all');
    setPrice('');
    setChangePct('');
    setMultiplier('');
    setWindow('20');
    setPeriod('12');
    setThreshold('');
    setFastPeriod('12');
    setSlowPeriod('26');
    setSignalPeriod('9');
    setKPeriod('3');
    setDPeriod('3');
    resetParameters(alertType);
    setEnabled(true);
  };

  const renderTargetControl = () => {
    if (targetScope === 'single_symbol') {
      return <Input label="종목 코드" value={target} onChange={(event) => setTarget(event.target.value)} placeholder="005930.KS / AAPL" disabled={isSubmitting} />;
    }
    if (targetScope === 'watchlist') {
      return <Input label="대상" value="default" onChange={() => undefined} disabled />;
    }
    return (
      <div className="space-y-2">
        <Select label="계좌" value={portfolioTarget} options={portfolioTargetOptions} disabled={isSubmitting} onChange={setPortfolioTarget} />
        {accountsError ? <p role="alert" className="text-xs text-warning">{accountsError}</p> : null}
      </div>
    );
  };

  return (
    <Card title="알림 규칙 만들기" subtitle="조건을 충족하면 알림을 보냅니다." variant="bordered" padding="md">
      <form className="space-y-4" noValidate onSubmit={(event) => void handleSubmit(event)}>
        <div className="grid gap-4 md:grid-cols-2">
          <Input label="규칙 이름" value={name} onChange={(event) => setName(event.target.value)} placeholder="예: 마오타이 가격 돌파" disabled={isSubmitting} />
          <Select label="대상 범위" value={targetScope} options={TARGET_SCOPE_OPTIONS} disabled={isSubmitting} onChange={handleScopeChange} />
          {renderTargetControl()}
          <Select label="규칙 유형" value={alertType} options={alertTypeOptions} disabled={isSubmitting} onChange={(value) => {
            const nextType = value as AlertType;
            setAlertType(nextType);
            resetParameters(nextType);
          }} />
          <Select label="심각도" value={severity} options={SEVERITY_OPTIONS} disabled={isSubmitting} onChange={(value) => setSeverity(value as AlertSeverity)} />
        </div>

        {alertType === 'price_cross' ? (
          <div className="grid gap-4 md:grid-cols-2">
            <Select label="방향" value={priceDirection} options={PRICE_DIRECTION_OPTIONS} disabled={isSubmitting} onChange={(value) => setPriceDirection(value as 'above' | 'below')} />
            <Input label="가격 임계값" type="number" min="0" step="0.0001" value={price} onChange={(event) => setPrice(event.target.value)} disabled={isSubmitting} />
          </div>
        ) : null}

        {alertType === 'price_change_percent' ? (
          <div className="grid gap-4 md:grid-cols-2">
            <Select label="방향" value={changeDirection} options={CHANGE_DIRECTION_OPTIONS} disabled={isSubmitting} onChange={(value) => setChangeDirection(value as 'up' | 'down')} />
            <Input label="등락률 임계값(%)" type="number" min="0" step="0.01" value={changePct} onChange={(event) => setChangePct(event.target.value)} disabled={isSubmitting} />
          </div>
        ) : null}

        {alertType === 'volume_spike' ? (
          <Input label="거래량 급증 배수" type="number" min="0" step="0.01" value={multiplier} onChange={(event) => setMultiplier(event.target.value)} disabled={isSubmitting} />
        ) : null}

        {alertType === 'ma_price_cross' ? (
          <div className="grid gap-4 md:grid-cols-2">
            <Select label="교차 방향" value={thresholdDirection} options={THRESHOLD_DIRECTION_OPTIONS} disabled={isSubmitting} onChange={(value) => setThresholdDirection(value as 'above' | 'below')} />
            <Input label="이동평균 기간" type="number" min="2" max="250" step="1" value={window} onChange={(event) => setWindow(event.target.value)} disabled={isSubmitting} />
          </div>
        ) : null}

        {alertType === 'rsi_threshold' || alertType === 'cci_threshold' ? (
          <div className="grid gap-4 md:grid-cols-3">
            <Select label="임계값 방향" value={thresholdDirection} options={THRESHOLD_DIRECTION_OPTIONS} disabled={isSubmitting} onChange={(value) => setThresholdDirection(value as 'above' | 'below')} />
            <Input label={alertType === 'rsi_threshold' ? 'RSI 기간' : 'CCI 기간'} type="number" min="2" max="250" step="1" value={period} onChange={(event) => setPeriod(event.target.value)} disabled={isSubmitting} />
            <Input label={alertType === 'rsi_threshold' ? 'RSI 임계값' : 'CCI 임계값'} type="number" min={alertType === 'rsi_threshold' ? '0' : undefined} max={alertType === 'rsi_threshold' ? '100' : undefined} step="0.01" value={threshold} onChange={(event) => setThreshold(event.target.value)} disabled={isSubmitting} />
          </div>
        ) : null}

        {alertType === 'macd_cross' ? (
          <div className="grid gap-4 md:grid-cols-4">
            <Select label="교차 방향" value={crossDirection} options={CROSS_DIRECTION_OPTIONS} disabled={isSubmitting} onChange={(value) => setCrossDirection(value as 'bullish_cross' | 'bearish_cross')} />
            <Input label="단기 기간" type="number" min="2" max="250" step="1" value={fastPeriod} onChange={(event) => setFastPeriod(event.target.value)} disabled={isSubmitting} />
            <Input label="장기 기간" type="number" min="2" max="250" step="1" value={slowPeriod} onChange={(event) => setSlowPeriod(event.target.value)} disabled={isSubmitting} />
            <Input label="시그널 기간" type="number" min="2" max="250" step="1" value={signalPeriod} onChange={(event) => setSignalPeriod(event.target.value)} disabled={isSubmitting} />
          </div>
        ) : null}

        {alertType === 'kdj_cross' ? (
          <div className="grid gap-4 md:grid-cols-4">
            <Select label="교차 방향" value={crossDirection} options={CROSS_DIRECTION_OPTIONS} disabled={isSubmitting} onChange={(value) => setCrossDirection(value as 'bullish_cross' | 'bearish_cross')} />
            <Input label="KDJ 기간" type="number" min="2" max="250" step="1" value={period} onChange={(event) => setPeriod(event.target.value)} disabled={isSubmitting} />
            <Input label="K 평활 기간" type="number" min="2" max="250" step="1" value={kPeriod} onChange={(event) => setKPeriod(event.target.value)} disabled={isSubmitting} />
            <Input label="D 평활 기간" type="number" min="2" max="250" step="1" value={dPeriod} onChange={(event) => setDPeriod(event.target.value)} disabled={isSubmitting} />
          </div>
        ) : null}

        {alertType === 'portfolio_stop_loss' ? (
          <Select label="손절 모드" value={stopLossMode} options={STOP_LOSS_MODE_OPTIONS} disabled={isSubmitting} onChange={(value) => setStopLossMode(value as PortfolioStopLossMode)} />
        ) : null}

        <Checkbox label="규칙 활성화" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} disabled={isSubmitting} />
        {formError ? <p role="alert" className="text-sm text-danger">{formError}</p> : null}
        <Button type="submit" isLoading={isSubmitting} loadingText="저장 중...">규칙 저장</Button>
      </form>
    </Card>
  );
};
