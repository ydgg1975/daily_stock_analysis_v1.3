// 推荐选股相关类型定义

export interface RecommendedStock {
  code: string;
  name: string;
  market: string;
  price?: number | null;
  changePct?: number | null;
  score?: number | null;
  reason?: string;
  risk?: string;
  targetPrice?: string;
  stopLoss?: string;
}

export interface RecommendationResult {
  taskId: string;
  markets: string;
  priceMin?: number | null;
  priceMax?: number | null;
  candidatesCount: number;
  stocks: RecommendedStock[];
  analysisSummary?: string;
  modelUsed?: string;
  createdAt?: string;
}

export interface RecommendTaskAccepted {
  taskId: string;
  status: string;
  message?: string;
}

export interface RecommendTaskStatus {
  taskId: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress?: number | null;
  result?: RecommendationResult | null;
  error?: string | null;
}

export interface RecommendHistoryItem {
  id: number;
  taskId: string;
  markets: string;
  priceMin?: number | null;
  priceMax?: number | null;
  stockCount: number;
  status: string;
  modelUsed?: string;
  createdAt?: string;
}

export interface RecommendHistoryResponse {
  total: number;
  items: RecommendHistoryItem[];
  limit: number;
  offset: number;
}
