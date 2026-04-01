import type React from 'react';
import { useEffect } from 'react';
import { MarketReviewPanel } from '../components/market';

const MarketReviewPage: React.FC = () => {
  useEffect(() => {
    document.title = '大盘复盘 - DSA';
  }, []);

  return (
    <div className="min-h-full px-4 pb-6 pt-4 md:px-6">
      <div className="max-w-7xl mx-auto">
        <MarketReviewPanel />
      </div>
    </div>
  );
};

export default MarketReviewPage;