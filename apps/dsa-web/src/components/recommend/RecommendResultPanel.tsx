import React from 'react';
import { Card, EmptyState, Loading, Badge } from '../common';
import { useRecommendStore } from '../../stores/recommendStore';
import { RecommendedStockCard } from './RecommendedStockCard';
import { Sparkles, AlertCircle } from 'lucide-react';

export const RecommendResultPanel: React.FC = () => {
  const { taskStatus, result, polling, error } = useRecommendStore();

  // Not started
  if (!taskStatus && !result && !error) {
    return (
      <Card className="flex min-h-[300px] items-center justify-center">
        <EmptyState
          title="AI 选股推荐"
          description="填写左侧条件并提交，AI 将从全市场中筛选推荐股票"
        />
      </Card>
    );
  }

  // Error
  if (error) {
    return (
      <Card className="space-y-3">
        <div className="flex items-center gap-2 text-danger">
          <AlertCircle className="h-5 w-5" />
          <span className="font-medium">推荐失败</span>
        </div>
        <p className="text-sm text-secondary-text">{error}</p>
      </Card>
    );
  }

  // Processing
  if (polling || (taskStatus && taskStatus.status !== 'completed' && taskStatus.status !== 'failed')) {
    const progress = taskStatus?.progress ?? 0;
    return (
      <Card className="flex min-h-[300px] flex-col items-center justify-center gap-4">
        <Loading />
        <div className="text-center">
          <p className="text-sm font-medium text-foreground">AI 正在分析推荐...</p>
          <p className="mt-1 text-xs text-secondary-text">进度: {progress}%</p>
        </div>
        <div className="w-48 h-1.5 rounded-full bg-border/30 overflow-hidden">
          <div
            className="h-full rounded-full bg-cyan transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
      </Card>
    );
  }

  // No result
  if (!result || result.stocks.length === 0) {
    return (
      <Card className="flex min-h-[300px] items-center justify-center">
        <EmptyState
          title="暂无推荐"
          description="AI 未能从当前候选中找到合适的推荐，请尝试调整筛选条件"
        />
      </Card>
    );
  }

  // Display results
  return (
    <div className="space-y-4">
      {/* Header */}
      <Card className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-cyan" />
            <h3 className="font-semibold text-foreground">推荐结果</h3>
          </div>
          <div className="flex items-center gap-2 text-xs text-secondary-text">
            <Badge variant="info" size="sm">
              候选 {result.candidatesCount} 只
            </Badge>
            <Badge variant="success" size="sm">
              推荐 {result.stocks.length} 只
            </Badge>
          </div>
        </div>
        {result.analysisSummary && (
          <p className="text-sm text-secondary-text leading-relaxed">
            {result.analysisSummary}
          </p>
        )}
        {result.modelUsed && (
          <p className="text-xs text-secondary-text/60">
            模型: {result.modelUsed}
          </p>
        )}
      </Card>

      {/* Stock cards */}
      <div className="space-y-3">
        {result.stocks.map((stock, index) => (
          <RecommendedStockCard key={stock.code} stock={stock} rank={index + 1} />
        ))}
      </div>
    </div>
  );
};
