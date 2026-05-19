import type React from 'react';
import { useState } from 'react';
import { Button, Card, Checkbox, Input, Select } from '../common';
import type { AlertRuleCreateRequest, AlertSeverity, AlertType } from '../../types/alerts';
import { validateStockCode } from '../../utils/validation';

const ALERT_TYPE_OPTIONS = [
  { value: 'price_cross', label: '가격 돌파' },
  { value: 'price_change_percent', label: '등락률' },
  { value: 'volume_spike', label: '거래량 급증' },
];

const SEVERITY_OPTIONS = [
  { value: 'info', label: '안내' },
  { value: 'warning', label: '경고' },
  { value: 'critical', label: '심각' },
];

const PRICE_DIRECTION_OPTIONS = [
  { value: 'above', label: '상향 돌파' },
  { value: 'below', label: '하향 돌파' },
];

const CHANGE_DIRECTION_OPTIONS = [
  { value: 'up', label: '상승 도달' },
  { value: 'down', label: '하락 도달' },
];

interface AlertRuleFormProps {
  onSubmit: (payload: AlertRuleCreateRequest) => Promise<boolean | void> | boolean | void;
  isSubmitting?: boolean;
}

export const AlertRuleForm: React.FC<AlertRuleFormProps> = ({ onSubmit, isSubmitting = false }) => {
  const [name, setName] = useState('');
  const [target, setTarget] = useState('');
  const [alertType, setAlertType] = useState<AlertType>('price_cross');
  const [severity, setSeverity] = useState<AlertSeverity>('warning');
  const [enabled, setEnabled] = useState(true);
  const [priceDirection, setPriceDirection] = useState<'above' | 'below'>('above');
  const [changeDirection, setChangeDirection] = useState<'up' | 'down'>('up');
  const [price, setPrice] = useState('');
  const [changePct, setChangePct] = useState('');
  const [multiplier, setMultiplier] = useState('');
  const [formError, setFormError] = useState<string | null>(null);

  const resetParameters = (nextType: AlertType) => {
    if (nextType === 'price_cross') {
      setPriceDirection('above');
      setPrice('');
    } else if (nextType === 'price_change_percent') {
      setChangeDirection('up');
      setChangePct('');
    } else {
      setMultiplier('');
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

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const targetValidation = validateStockCode(target);
    if (!targetValidation.valid) {
      setFormError(targetValidation.message ?? '종목 코드 형식이 올바르지 않습니다.');
      return;
    }

    let parameters: AlertRuleCreateRequest['parameters'];
    if (alertType === 'price_cross') {
      const parsedPrice = parsePositiveNumber(price, '가격 임계값');
      if (parsedPrice == null) return;
      parameters = { direction: priceDirection, price: parsedPrice };
    } else if (alertType === 'price_change_percent') {
      const parsedChangePct = parsePositiveNumber(changePct, '등락률 임계값');
      if (parsedChangePct == null) return;
      parameters = { direction: changeDirection, changePct: parsedChangePct };
    } else {
      const parsedMultiplier = parsePositiveNumber(multiplier, '거래량 배수');
      if (parsedMultiplier == null) return;
      parameters = { multiplier: parsedMultiplier };
    }

    setFormError(null);
    const submitted = await onSubmit({
      name: name.trim() || undefined,
      targetScope: 'single_symbol',
      target: targetValidation.normalized,
      alertType,
      parameters,
      severity,
      enabled,
    });
    if (submitted === false) return;
    setName('');
    setTarget('');
    setPrice('');
    setChangePct('');
    setMultiplier('');
    setEnabled(true);
  };

  return (
    <Card title="알림 규칙 만들기" subtitle="Web 알림 필터" variant="bordered" padding="md">
      <form className="space-y-4" onSubmit={(event) => void handleSubmit(event)}>
        <div className="grid gap-4 md:grid-cols-2">
          <Input
            label="규칙 이름"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="선택 사항, 예: 600519 가격 돌파"
            disabled={isSubmitting}
          />
          <Input
            label="종목 코드"
            value={target}
            onChange={(event) => setTarget(event.target.value)}
            placeholder="600519 / AAPL / hk00700"
            disabled={isSubmitting}
          />
          <Select
            label="규칙 유형"
            value={alertType}
            options={ALERT_TYPE_OPTIONS}
            disabled={isSubmitting}
            onChange={(value) => {
              const nextType = value as AlertType;
              setAlertType(nextType);
              resetParameters(nextType);
            }}
          />
          <Select
            label="심각도"
            value={severity}
            options={SEVERITY_OPTIONS}
            disabled={isSubmitting}
            onChange={(value) => setSeverity(value as AlertSeverity)}
          />
        </div>

        {alertType === 'price_cross' ? (
          <div className="grid gap-4 md:grid-cols-2">
            <Select
              label="방향"
              value={priceDirection}
              options={PRICE_DIRECTION_OPTIONS}
              disabled={isSubmitting}
              onChange={(value) => setPriceDirection(value as 'above' | 'below')}
            />
            <Input
              label="가격 임계값"
              type="number"
              min="0"
              step="0.0001"
              value={price}
              onChange={(event) => setPrice(event.target.value)}
              disabled={isSubmitting}
            />
          </div>
        ) : null}

        {alertType === 'price_change_percent' ? (
          <div className="grid gap-4 md:grid-cols-2">
            <Select
              label="방향"
              value={changeDirection}
              options={CHANGE_DIRECTION_OPTIONS}
              disabled={isSubmitting}
              onChange={(value) => setChangeDirection(value as 'up' | 'down')}
            />
            <Input
              label="등락률 임계값(%)"
              type="number"
              min="0"
              step="0.01"
              value={changePct}
              onChange={(event) => setChangePct(event.target.value)}
              disabled={isSubmitting}
            />
          </div>
        ) : null}

        {alertType === 'volume_spike' ? (
          <Input
            label="거래량 배수"
            type="number"
            min="0"
            step="0.01"
            value={multiplier}
            onChange={(event) => setMultiplier(event.target.value)}
            disabled={isSubmitting}
          />
        ) : null}

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <Checkbox
            label="생성 후 바로 활성화"
            checked={enabled}
            onChange={(event) => setEnabled(event.target.checked)}
            disabled={isSubmitting}
          />
          <Button type="submit" isLoading={isSubmitting} loadingText="생성 중...">
            규칙 만들기
          </Button>
        </div>
        {formError ? <p role="alert" className="text-sm text-danger">{formError}</p> : null}
      </form>
    </Card>
  );
};
