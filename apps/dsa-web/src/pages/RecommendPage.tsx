import React, { useEffect } from 'react';
import { ApiErrorAlert } from '../components/common';
import { createParsedApiError } from '../api/error';
import { RecommendForm } from '../components/recommend/RecommendForm';
import { RecommendResultPanel } from '../components/recommend/RecommendResultPanel';
import { RecommendHistoryList } from '../components/recommend/RecommendHistoryList';
import { useRecommendStore } from '../stores/recommendStore';
import { Sparkles } from 'lucide-react';

const RecommendPage: React.FC = () => {
  const { error, clearError, stopPolling, loadHistory } = useRecommendStore();

  useEffect(() => {
    loadHistory();
    return () => {
      stopPolling();
    };
  }, [loadHistory, stopPolling]);

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
      {/* Page header */}
      <div className="mb-6 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-cyan/10">
          <Sparkles className="h-5 w-5 text-cyan" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-foreground">AI 选股推荐</h1>
          <p className="text-sm text-secondary-text">
            基于市场行情、舆情资料和 AI 分析，推荐 3~5 只值得关注的股票
          </p>
        </div>
      </div>

      {/* Error alert */}
      {error && (
        <div className="mb-4">
          <ApiErrorAlert error={createParsedApiError({ title: '操作失败', message: error })} onDismiss={clearError} />
        </div>
      )}

      {/* Main content: form + result */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
        {/* Left: Form */}
        <div className="lg:col-span-2">
          <RecommendForm />
        </div>

        {/* Right: Result */}
        <div className="lg:col-span-3">
          <RecommendResultPanel />
        </div>
      </div>

      {/* History */}
      <div className="mt-8">
        <RecommendHistoryList />
      </div>
    </div>
  );
};

export default RecommendPage;
