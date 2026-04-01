import type React from 'react';
import { useEffect, useState, useCallback } from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { historyApi } from '../../api/history';
import { Drawer } from '../common/Drawer';
import { SupportPanel } from '../common';
import { getReportText, normalizeReportLanguage } from '../../utils/reportLanguage';
import type { ReportLanguage } from '../../types/analysis';

interface ReportMarkdownProps {
  recordId: number;
  stockName: string;
  stockCode: string;
  onClose: () => void;
  reportLanguage?: ReportLanguage;
}

/**
 * Markdown 报告抽屉组件
 * 使用通用 Drawer 组件，展示完整的 Markdown 格式分析报告
 */
export const ReportMarkdown: React.FC<ReportMarkdownProps> = ({
  recordId,
  stockName,
  stockCode,
  onClose,
  reportLanguage = 'zh',
}) => {
  const text = getReportText(normalizeReportLanguage(reportLanguage));
  const loadReportFailedText = text.loadReportFailed;
  const [content, setContent] = useState<string>('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(true);

  // Handle close with animation
  const handleClose = useCallback(() => {
    setIsOpen(false);
    // Delay actual close to allow animation to complete
    setTimeout(onClose, 300);
  }, [onClose]);

  useEffect(() => {
    let isMounted = true;

    const fetchMarkdown = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const markdownContent = await historyApi.getMarkdown(recordId);
        if (isMounted) {
          setContent(markdownContent);
        }
      } catch (err) {
        if (isMounted) {
          setError(err instanceof Error ? err.message : loadReportFailedText);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    fetchMarkdown();

    return () => {
      isMounted = false;
    };
  }, [recordId, loadReportFailedText]);

  return (
    <Drawer isOpen={isOpen} onClose={handleClose} width="max-w-3xl" zIndex={100}>
      <SupportPanel
        className="mb-4"
        title={stockName || stockCode}
        body={text.fullReport}
        icon={(
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--home-action-report-bg)] text-[var(--home-action-report-text)]">
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
        )}
        titleClassName="mt-0 text-base font-semibold"
      >
        <p className="text-xs leading-5 text-muted-text">
          这里展示的是原始 Markdown 版本，适合完整阅读、复制或与卡片化报告互相校对。
        </p>
      </SupportPanel>

      {isLoading ? (
        <SupportPanel
          centered
          className="flex h-64 flex-col items-center justify-center px-6 py-6"
          icon={<div className="home-spinner h-10 w-10 animate-spin border-[3px]" />}
          title={text.loadingReport}
          body="正在拉取 Markdown 内容，请稍候。"
        />
      ) : error ? (
        <SupportPanel
          centered
          className="flex h-64 flex-col items-center justify-center px-6 py-6"
          icon={(
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-danger/10">
              <svg className="h-6 w-6 text-danger" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
          )}
          title={error}
          body="可以关闭抽屉后重新打开，或稍后再试。"
          titleClassName="text-danger"
          actions={(
            <button
              type="button"
              onClick={handleClose}
              className="home-surface-button rounded-lg px-4 py-2 text-sm text-secondary-text"
            >
              {text.dismiss}
            </button>
          )}
        />
      ) : (
        <SupportPanel className="px-4 py-4">
          <div
            className="home-markdown-prose prose prose-invert prose-sm max-w-none
              prose-headings:text-foreground prose-headings:font-semibold prose-headings:mt-4 prose-headings:mb-2
              prose-h1:text-xl
              prose-h2:text-lg
              prose-h3:text-base
              prose-p:leading-relaxed prose-p:mb-3 prose-p:last:mb-0
              prose-strong:text-foreground prose-strong:font-semibold
              prose-ul:my-2 prose-ol:my-2 prose-li:my-1
              prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:before:content-none prose-code:after:content-none
              prose-pre:border
              prose-table:border-collapse
              prose-th:border prose-th:px-3 prose-th:py-2
              prose-td:border prose-td:px-3 prose-td:py-2
              prose-hr:my-4
              prose-a:no-underline hover:prose-a:underline
              prose-blockquote:text-secondary-text
              whitespace-pre-line break-words
            "
          >
            <Markdown remarkPlugins={[remarkGfm]}>
              {content}
            </Markdown>
          </div>
        </SupportPanel>
      )}

      {/* Footer */}
      <div className="home-divider mt-6 flex justify-end border-t pt-4">
        <button
          type="button"
          onClick={handleClose}
          className="home-surface-button rounded-lg px-4 py-2 text-sm text-secondary-text hover:text-foreground"
        >
          {text.dismiss}
        </button>
      </div>
    </Drawer>
  );
};
