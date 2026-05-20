import type React from 'react';
import { useCallback, useRef, useState } from 'react';
import { getParsedApiError } from '../../api/error';
import { stocksApi, type ExtractItem } from '../../api/stocks';
import { systemConfigApi, SystemConfigConflictError } from '../../api/systemConfig';
import { Badge, Button, InlineAlert } from '../common';

const IMG_EXT = ['.jpg', '.jpeg', '.png', '.webp', '.gif'];
const IMG_MAX = 5 * 1024 * 1024; // 5MB
const FILE_MAX = 2 * 1024 * 1024; // 2MB
const TEXT_MAX = 100 * 1024; // 100KB

interface IntelligentImportProps {
  stockListValue: string;
  configVersion: string;
  maskToken: string;
  onMerged: (newValue: string) => void | Promise<void>;
  disabled?: boolean;
}

type ItemWithChecked = ExtractItem & { id: string; checked: boolean };

function getConfidenceMeta(confidence: 'high' | 'medium' | 'low') {
  if (confidence === 'high') {
    return { label: '높음', badge: 'success' as const };
  }
  if (confidence === 'low') {
    return { label: '낮음', badge: 'warning' as const };
  }
  return { label: '중간', badge: 'default' as const };
}

function normalizeConfidence(confidence?: string | null): 'high' | 'medium' | 'low' {
  if (confidence === 'high' || confidence === 'low' || confidence === 'medium') {
    return confidence;
  }
  return 'medium';
}

function mergeItems(
  prev: ItemWithChecked[],
  newItems: ExtractItem[]
): ItemWithChecked[] {
  const byCode = new Map<string, ItemWithChecked>();
  const confOrder: Record<'high' | 'medium' | 'low', number> = {
    high: 3,
    medium: 2,
    low: 1,
  };
  const failed: ItemWithChecked[] = [];
  for (const p of prev) {
    if (p.code) {
      byCode.set(p.code, p);
    } else {
      failed.push(p);
    }
  }
  for (const it of newItems) {
    const normalizedConfidence = normalizeConfidence(it.confidence);
    if (it.code) {
      const existing = byCode.get(it.code);
      if (!existing) {
        byCode.set(it.code, {
          ...it,
          confidence: normalizedConfidence,
          id: `${it.code}-${Date.now()}-${Math.random().toString(36).slice(2)}`,
          checked: normalizedConfidence === 'high',
        });
      } else {
        const existingConfidence = normalizeConfidence(existing.confidence);
        const shouldUpgradeConfidence = confOrder[normalizedConfidence] > confOrder[existingConfidence];
        const shouldFillName = !existing.name && !!it.name;

        if (shouldUpgradeConfidence || shouldFillName) {
          byCode.set(it.code, {
            ...existing,
            name: it.name || existing.name,
            confidence: shouldUpgradeConfidence ? normalizedConfidence : existingConfidence,
            checked: shouldUpgradeConfidence
              ? (normalizedConfidence === 'high' ? true : existing.checked)
              : existing.checked,
          });
        }
      }
    } else {
      failed.push({
        ...it,
        confidence: normalizedConfidence,
        id: `fail-${Date.now()}-${Math.random().toString(36).slice(2)}`,
        checked: false,
      });
    }
  }
  return [...byCode.values(), ...failed];
}

export const IntelligentImport: React.FC<IntelligentImportProps> = ({
  stockListValue,
  configVersion,
  maskToken,
  onMerged,
  disabled,
}) => {
  const [items, setItems] = useState<ItemWithChecked[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isMerging, setIsMerging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [pasteText, setPasteText] = useState('');
  const imageInputRef = useRef<HTMLInputElement | null>(null);
  const dataFileInputRef = useRef<HTMLInputElement | null>(null);

  const parseCurrentList = useCallback(() => {
    return stockListValue
      .split(',')
      .map((c) => c.trim())
      .filter(Boolean);
  }, [stockListValue]);

  const addItems = useCallback((newItems: ExtractItem[]) => {
    setItems((prev) => mergeItems(prev, newItems));
  }, []);

  const handleImageFile = useCallback(
    async (file: File) => {
      const ext = '.' + (file.name.split('.').pop() ?? '').toLowerCase();
      if (!IMG_EXT.includes(ext)) {
        setError('이미지는 JPG, PNG, WebP, GIF만 지원합니다');
        return;
      }
      if (file.size > IMG_MAX) {
        setError('이미지는 5MB를 넘을 수 없습니다');
        return;
      }
      setError(null);
      setIsLoading(true);
      try {
        const res = await stocksApi.extractFromImage(file);
        addItems(res.items ?? res.codes.map((c) => ({ code: c, name: null, confidence: 'medium' })));
      } catch (e) {
        const parsed = getParsedApiError(e);
        const err = e && typeof e === 'object' ? (e as { response?: { status?: number }; code?: string }) : null;
        let fallback = '인식에 실패했습니다. 다시 시도하세요';
        if (err?.response?.status === 429) fallback = '요청이 너무 많습니다. 잠시 후 다시 시도하세요';
        else if (err?.code === 'ECONNABORTED') fallback = '요청 시간이 초과되었습니다. 네트워크를 확인한 뒤 다시 시도하세요';
        setError(parsed.message || fallback);
      } finally {
        setIsLoading(false);
      }
    },
    [addItems],
  );

  const handleDataFile = useCallback(
    async (file: File) => {
      if (file.size > FILE_MAX) {
        setError('파일은 2MB를 넘을 수 없습니다');
        return;
      }
      setError(null);
      setIsLoading(true);
      try {
        const res = await stocksApi.parseImport(file);
        addItems(res.items ?? res.codes.map((c) => ({ code: c, name: null, confidence: 'medium' })));
      } catch (e) {
        const parsed = getParsedApiError(e);
        setError(parsed.message || '파싱 실패');
      } finally {
        setIsLoading(false);
      }
    },
    [addItems],
  );

  const handlePasteParse = useCallback(() => {
    const t = pasteText.trim();
    if (!t) return;
    if (new Blob([t]).size > TEXT_MAX) {
      setError('붙여넣은 텍스트는 100KB를 넘을 수 없습니다');
      return;
    }
    setError(null);
    setIsLoading(true);
    stocksApi
      .parseImport(undefined, t)
      .then((res) => {
        addItems(res.items ?? res.codes.map((c) => ({ code: c, name: null, confidence: 'medium' })));
        setPasteText('');
      })
      .catch((e) => {
        const parsed = getParsedApiError(e);
        setError(parsed.message || '파싱 실패');
      })
      .finally(() => setIsLoading(false));
  }, [pasteText, addItems]);

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      if (disabled || isLoading) return;
      const f = e.dataTransfer?.files?.[0];
      if (!f) return;
      const ext = '.' + (f.name.split('.').pop() ?? '').toLowerCase();
      if (IMG_EXT.includes(ext)) void handleImageFile(f);
      else void handleDataFile(f);
    },
    [disabled, isLoading, handleImageFile, handleDataFile],
  );

  const onImageInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const f = e.target.files?.[0];
      if (f) void handleImageFile(f);
      e.target.value = '';
    },
    [handleImageFile],
  );

  const onDataFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const f = e.target.files?.[0];
      if (f) void handleDataFile(f);
      e.target.value = '';
    },
    [handleDataFile],
  );

  const openFilePicker = useCallback((inputRef: React.RefObject<HTMLInputElement | null>) => {
    if (disabled || isLoading) {
      return;
    }
    inputRef.current?.click();
  }, [disabled, isLoading]);

  const toggleChecked = useCallback((id: string) => {
    setItems((prev) => prev.map((p) => (p.id === id && p.code ? { ...p, checked: !p.checked } : p)));
  }, []);

  const toggleAll = useCallback((checked: boolean) => {
    setItems((prev) => prev.map((p) => (p.code ? { ...p, checked } : p)));
  }, []);

  const removeItem = useCallback((id: string) => {
    setItems((prev) => prev.filter((p) => p.id !== id));
  }, []);

  const clearAll = useCallback(() => {
    setItems([]);
    setPasteText('');
    setError(null);
  }, []);

  const mergeToWatchlist = useCallback(async () => {
    const toMerge = items.filter((i) => i.checked && i.code).map((i) => i.code!);
    if (toMerge.length === 0) return;
    if (!configVersion) {
      setError('설정을 먼저 불러온 뒤 병합하세요');
      return;
    }
    const current = parseCurrentList();
    const merged = [...new Set([...current, ...toMerge])];
    const value = merged.join(',');

    setIsMerging(true);
    setError(null);
    try {
      await systemConfigApi.update({
        configVersion,
        maskToken,
        reloadNow: true,
        items: [{ key: 'STOCK_LIST', value }],
      });
      setItems([]);
      setPasteText('');
      await onMerged(value);
    } catch (e) {
      if (e instanceof SystemConfigConflictError) {
        await onMerged(value);
        setError('설정이 업데이트되었습니다. 관심 종목에 병합을 다시 누르세요');
      } else {
        setError(e instanceof Error ? e.message : '병합 저장 실패');
      }
    } finally {
      setIsMerging(false);
    }
  }, [items, configVersion, maskToken, onMerged, parseCurrentList]);

  const validCount = items.filter((i) => i.code).length;
  const checkedCount = items.filter((i) => i.checked && i.code).length;

  return (
    <div className="space-y-4">
      <div className="settings-surface-panel settings-border-strong rounded-xl border p-4 shadow-soft-card">
        <p className="text-sm font-medium text-foreground">이미지, CSV/Excel 파일, 클립보드 텍스트를 지원합니다</p>
        <p className="mt-1 text-xs leading-5 text-secondary-text">
          이미지 인식은 Vision 모델 설정이 필요합니다. 결과를 직접 확인한 뒤 관심 종목에 병합하는 것을 권장합니다.
        </p>
      </div>

      <div
        onDrop={onDrop}
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={(e) => { e.preventDefault(); setIsDragging(false); }}
        className={`flex min-h-[96px] flex-col gap-4 rounded-xl border border-dashed  p-4 transition-colors ${
          isDragging ? 'settings-drag-active' : 'settings-border-strong settings-surface-overlay-soft'
        } ${disabled || isLoading ? 'cursor-not-allowed opacity-60' : ''}`}
      >
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            variant="settings-secondary"
            disabled={disabled || isLoading}
            onClick={() => openFilePicker(imageInputRef)}
          >
            이미지 선택
          </Button>
          <input
            ref={imageInputRef}
            type="file"
            accept=".jpg,.jpeg,.png,.webp,.gif"
            className="hidden"
            onChange={onImageInput}
            disabled={disabled || isLoading}
          />
          <Button
            type="button"
            variant="settings-secondary"
            disabled={disabled || isLoading}
            onClick={() => openFilePicker(dataFileInputRef)}
          >
            파일 선택
          </Button>
          <input
            ref={dataFileInputRef}
            type="file"
            accept=".csv,.xlsx,.txt"
            className="hidden"
            onChange={onDataFileInput}
            disabled={disabled || isLoading}
          />
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <textarea
            placeholder="또는 CSV/Excel에서 복사한 텍스트를 붙여넣기..."
            className="input-surface settings-surface-strong settings-border-strong min-h-[72px] w-full rounded-xl border px-3 py-2 text-sm text-foreground shadow-none transition-colors placeholder:text-muted-text focus:outline-none"
            value={pasteText}
            onChange={(e) => setPasteText(e.target.value)}
            disabled={disabled || isLoading}
          />
          <Button
            type="button"
            variant="settings-secondary"
            className="shrink-0 sm:self-start"
            onClick={handlePasteParse}
            disabled={disabled || isLoading || !pasteText.trim()}
          >
            파싱
          </Button>
        </div>
      </div>

      {isLoading && <p className="text-sm text-secondary-text">처리 중...</p>}
      {error && (
        <InlineAlert
          variant="danger"
          message={error}
          className="rounded-xl px-3 py-2 text-sm shadow-none"
        />
      )}

      {items.length > 0 && (
        <div className="space-y-2">
          <InlineAlert
            variant="warning"
            message="병합할 항목을 직접 확인하는 것을 권장합니다. 신뢰도 높음은 기본 선택되고, 중간/낮음은 수동 확인이 필요합니다."
            className="rounded-xl px-3 py-2 text-xs shadow-none"
          />
          <div className="flex items-center justify-between">
            <span className="text-xs text-secondary-text">
              총 {validCount}개 병합 가능 · 선택됨 {checkedCount}개
            </span>
            <div className="flex gap-2">
              <button type="button" className="text-xs text-secondary-text transition-colors hover:text-foreground" onClick={() => toggleAll(true)}>
                전체 선택
              </button>
              <button type="button" className="text-xs text-secondary-text transition-colors hover:text-foreground" onClick={() => toggleAll(false)}>
                취소
              </button>
              <button type="button" className="text-xs text-secondary-text transition-colors hover:text-foreground" onClick={clearAll}>
                비우기
              </button>
            </div>
          </div>
          <div className="max-h-[220px] space-y-1 overflow-y-auto rounded-xl border settings-border-strong settings-surface-overlay-soft p-2">
            {items.map((it) => {
              const confidence = normalizeConfidence(it.confidence);
              const confidenceMeta = getConfidenceMeta(confidence);

              return (
                <div
                  key={it.id}
                  className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-sm ${
                    it.code ? 'settings-border bg-[var(--settings-surface-strong)]' : 'border-danger/25 bg-danger/10'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={it.checked}
                    onChange={() => toggleChecked(it.id)}
                    disabled={!it.code || disabled}
                    className="settings-input-checkbox h-4 w-4 rounded border-border/70 bg-base"
                  />
                  <span className={it.code ? 'font-medium text-foreground' : 'font-medium text-danger'}>
                    {it.code || '파싱 실패'}
                  </span>
                  {it.name && <span className="text-secondary-text">({it.name})</span>}
                  <div className="ml-auto flex items-center gap-2">
                    <Badge variant={confidenceMeta.badge} size="sm">
                      {confidenceMeta.label}
                    </Badge>
                    <button
                      type="button"
                      className="text-secondary-text transition-colors hover:text-foreground"
                      onClick={() => removeItem(it.id)}
                      disabled={disabled}
                    >
                      삭제
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
          <Button
            type="button"
            variant="primary"
            className="mt-2"
            onClick={() => void mergeToWatchlist()}
            disabled={disabled || isMerging || checkedCount === 0}
          >
            {isMerging ? '저장 중...' : '관심 종목에 병합'}
          </Button>
        </div>
      )}
    </div>
  );
};
