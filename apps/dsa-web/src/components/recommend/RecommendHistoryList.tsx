import React, { useEffect } from 'react';
import { Card, Badge, EmptyState, Loading } from '../common';
import { useRecommendStore } from '../../stores/recommendStore';
import { Clock, CheckCircle2, XCircle } from 'lucide-react';

function formatDate(iso?: string) {
  if (!iso) return '-';
  try {
    const d = new Date(iso);
    return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
  } catch {
    return iso;
  }
}

function statusBadge(status: string) {
  switch (status) {
    case 'completed':
      return (
        <Badge variant="success" size="sm">
          <CheckCircle2 className="h-3 w-3" /> 完成
        </Badge>
      );
    case 'failed':
      return (
        <Badge variant="danger" size="sm">
          <XCircle className="h-3 w-3" /> 失败
        </Badge>
      );
    case 'processing':
      return <Badge variant="info" size="sm">分析中</Badge>;
    default:
      return <Badge variant="default" size="sm">{status}</Badge>;
  }
}

const MARKET_LABELS: Record<string, string> = {
  a_share: 'A 股',
  hk: '港股',
  us: '美股',
};

function marketsDisplay(markets: string) {
  return markets
    .split(',')
    .map((m) => MARKET_LABELS[m.trim()] || m.trim())
    .join(' / ');
}

export const RecommendHistoryList: React.FC = () => {
  const { history, historyTotal, historyLoading, loadHistory } = useRecommendStore();

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  if (historyLoading && history.length === 0) {
    return (
      <Card className="flex items-center justify-center py-8">
        <Loading />
      </Card>
    );
  }

  if (history.length === 0) {
    return (
      <Card>
        <EmptyState title="暂无历史" description="提交推荐任务后，历史记录将显示在此" />
      </Card>
    );
  }

  return (
    <Card className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Clock className="h-4 w-4 text-secondary-text" />
          <span className="text-sm font-medium text-foreground">
            历史记录 ({historyTotal})
          </span>
        </div>
      </div>
      <div className="space-y-2">
        {history.map((item) => (
          <div
            key={item.id}
            className="flex items-center justify-between rounded-xl border border-border/40 bg-elevated/30 px-4 py-3 text-sm"
          >
            <div className="flex items-center gap-3">
              {statusBadge(item.status)}
              <span className="text-foreground">{marketsDisplay(item.markets)}</span>
              {item.stockCount > 0 && (
                <span className="text-xs text-secondary-text">
                  推荐 {item.stockCount} 只
                </span>
              )}
            </div>
            <span className="text-xs text-secondary-text">{formatDate(item.createdAt)}</span>
          </div>
        ))}
      </div>
    </Card>
  );
};
