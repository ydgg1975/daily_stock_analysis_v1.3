import React from 'react';
import { Card, Button } from '../common';
import { useRecommendStore } from '../../stores/recommendStore';
import { MarketSelector } from './MarketSelector';
import { PriceRangeInput } from './PriceRangeInput';
import { UrlListInput } from './UrlListInput';
import { SentimentFileUpload } from './SentimentFileUpload';
import { Sparkles, RotateCcw } from 'lucide-react';

export const RecommendForm: React.FC = () => {
  const {
    markets,
    priceMin,
    priceMax,
    urls,
    note,
    files,
    submitting,
    polling,
    setMarkets,
    setPriceMin,
    setPriceMax,
    setUrls,
    setNote,
    setFiles,
    submit,
    resetForm,
  } = useRecommendStore();

  const isDisabled = submitting || polling;

  return (
    <Card className="space-y-6">
      {/* Market selection */}
      <div className="space-y-2">
        <label className="text-sm font-medium text-foreground">目标市场 *</label>
        <MarketSelector selected={markets} onChange={setMarkets} />
      </div>

      {/* Price range */}
      <div className="space-y-2">
        <label className="text-sm font-medium text-foreground">价格区间</label>
        <PriceRangeInput
          min={priceMin}
          max={priceMax}
          onMinChange={setPriceMin}
          onMaxChange={setPriceMax}
        />
        <p className="text-xs text-secondary-text">留空表示不限制价格</p>
      </div>

      {/* URL list */}
      <div className="space-y-2">
        <label className="text-sm font-medium text-foreground">舆情 URL</label>
        <UrlListInput urls={urls} onChange={setUrls} />
      </div>

      {/* File upload */}
      <div className="space-y-2">
        <label className="text-sm font-medium text-foreground">舆情文件</label>
        <SentimentFileUpload files={files} onChange={setFiles} />
      </div>

      {/* Note */}
      <div className="space-y-2">
        <label className="text-sm font-medium text-foreground">补充说明</label>
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="例如：关注新能源板块、偏好低估值蓝筹股..."
          maxLength={2000}
          rows={3}
          className="w-full rounded-xl border border-border/70 bg-base px-4 py-3 text-sm text-foreground placeholder:text-secondary-text/50 focus:border-cyan/50 focus:outline-none focus:ring-2 focus:ring-cyan/15 transition-all resize-none"
        />
        <p className="text-xs text-secondary-text text-right">{note.length}/2000</p>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3 pt-2">
        <Button
          variant="primary"
          size="lg"
          onClick={submit}
          isLoading={submitting || polling}
          loadingText={polling ? '分析中...' : '提交中...'}
          disabled={isDisabled || markets.length === 0}
          className="flex-1"
          glow
        >
          <Sparkles className="h-4 w-4" />
          AI 选股推荐
        </Button>
        <Button
          variant="ghost"
          size="lg"
          onClick={resetForm}
          disabled={isDisabled}
        >
          <RotateCcw className="h-4 w-4" />
        </Button>
      </div>
    </Card>
  );
};
