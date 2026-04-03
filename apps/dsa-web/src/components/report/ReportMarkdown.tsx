import type React from 'react';
import { useEffect, useState, useCallback, useMemo } from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { historyApi } from '../../api/history';
import { Drawer } from '../common/Drawer';
import { SupportPanel } from '../common';
import { getReportText, normalizeReportLanguage } from '../../utils/reportLanguage';
import { localizeReportHeadingLabel, localizeReportTermLabel } from '../../utils/reportTerminology';
import type { ReportLanguage, StandardReport } from '../../types/analysis';
import {
  buildMissingFieldAudit,
  collectMissingFieldEntriesFromMarkdown,
  collectMissingFieldEntriesFromStandardReport,
  type MissingFieldCategory,
} from './missingFieldAudit';

interface ReportMarkdownProps {
  recordId: number;
  stockName: string;
  stockCode: string;
  onClose: () => void;
  reportLanguage?: ReportLanguage;
  standardReport?: StandardReport;
  initialContent?: string;
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
  standardReport,
  initialContent,
}) => {
  const normalizedLanguage = normalizeReportLanguage(reportLanguage);
  const text = getReportText(normalizedLanguage);
  const headingClassName = normalizedLanguage === 'en'
    ? 'text-sm font-semibold uppercase tracking-[0.12em]'
    : 'text-sm font-semibold tracking-[0.06em]';
  const captionClassName = normalizedLanguage === 'en'
    ? 'text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-text'
    : 'text-xs font-semibold tracking-[0.08em] text-muted-text';
  const colon = normalizedLanguage === 'en' ? ': ' : '：';
  const loadReportFailedText = text.loadReportFailed;
  const [content, setContent] = useState<string>(initialContent ?? '');
  const [isLoading, setIsLoading] = useState(initialContent === undefined);
  const [error, setError] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(true);

  const coverageAudit = useMemo(() => {
    const mergedEntries = [
      ...collectMissingFieldEntriesFromStandardReport(standardReport),
      ...collectMissingFieldEntriesFromMarkdown(content),
    ];
    return buildMissingFieldAudit(mergedEntries);
  }, [content, standardReport]);

  const localizedMarkdownContent = useMemo(() => {
    if (normalizedLanguage !== 'zh') {
      return content;
    }

    const translateTableHeaderLine = (line: string): string => {
      if (!line.trim().startsWith('|')) {
        return line;
      }
      return line
        .replace(/\bField\b/gi, '字段')
        .replace(/\bValue\b/gi, '数值')
        .replace(/\bBasis\b/gi, '口径')
        .replace(/\bSource\b/gi, '来源')
        .replace(/\bStatus\b/gi, '状态')
        .replace(/\bMissing Cause\b/gi, '缺失原因')
        .replace(/\bPriority\b/gi, '优先级');
    };

    return content
      .split('\n')
      .map((line) => {
        const headingMatch = line.match(/^(\s{0,3}#{1,6}\s+)(.+)$/);
        if (headingMatch?.[1] && headingMatch?.[2]) {
          const translatedHeading = localizeReportHeadingLabel(headingMatch[2], 'zh');
          return `${headingMatch[1]}${translatedHeading}`;
        }

        const bulletBoldMatch = line.match(/^(\s*[-*+]\s+\*\*)([^*]+)(\*\*\s*[:：]?\s*)(.*)$/);
        if (bulletBoldMatch?.[1] && bulletBoldMatch?.[2] && bulletBoldMatch?.[3]) {
          const translatedLabel = localizeReportHeadingLabel(bulletBoldMatch[2], 'zh');
          return `${bulletBoldMatch[1]}${translatedLabel}${bulletBoldMatch[3]}${bulletBoldMatch[4] || ''}`;
        }

        const bulletPlainMatch = line.match(/^(\s*[-*+]\s+)(.+)$/);
        if (bulletPlainMatch?.[1] && bulletPlainMatch?.[2]) {
          const translatedLabel = localizeReportHeadingLabel(bulletPlainMatch[2], 'zh');
          if (translatedLabel !== bulletPlainMatch[2]) {
            return `${bulletPlainMatch[1]}${translatedLabel}`;
          }
        }

        return translateTableHeaderLine(line);
      })
      .join('\n');
  }, [content, normalizedLanguage]);

  const coverageBuckets = coverageAudit.buckets.filter((bucket) => bucket.entries.length > 0);

  const coverageCategoryLabel = useCallback((category: MissingFieldCategory): string => {
    if (category === 'integrated_unavailable') {
      return text.missingIntegratedUnavailable;
    }
    if (category === 'not_integrated_yet') {
      return text.missingNotIntegratedYet;
    }
    if (category === 'source_not_provided') {
      return text.missingSourceNotProvided;
    }
    if (category === 'not_applicable') {
      return text.missingNotApplicable;
    }
    return text.missingOther;
  }, [text]);

  // Handle close with animation
  const handleClose = useCallback(() => {
    setIsOpen(false);
    // Delay actual close to allow animation to complete
    setTimeout(onClose, 300);
  }, [onClose]);

  useEffect(() => {
    if (initialContent !== undefined) {
      setContent(initialContent);
      setIsLoading(false);
      setError(null);
      return;
    }

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
  }, [initialContent, recordId, loadReportFailedText]);

  return (
    <Drawer isOpen={isOpen} onClose={handleClose} width="max-w-[min(96vw,112rem)]" zIndex={100}>
      <div className="mx-auto w-full max-w-[72rem] space-y-5 pb-1" data-testid="full-report-document-shell">
        <SupportPanel
          className="mb-1 px-5 py-4 md:px-6"
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
          bodyClassName="text-sm"
        >
          <p className="text-xs leading-5 text-muted-text">
            {text.markdownRawHint}
          </p>
        </SupportPanel>

        {isLoading ? (
          <SupportPanel
            centered
            className="flex h-64 flex-col items-center justify-center px-6 py-6"
            icon={<div className="home-spinner h-10 w-10 animate-spin border-[3px]" />}
            title={text.loadingReport}
            body={text.markdownLoadingBody}
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
            body={text.markdownErrorBody}
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
          <div className="space-y-5" data-testid="full-report-reading-surface">
            <SupportPanel
              className="px-5 py-4 md:px-6"
              title={text.coverageAuditTitle}
              body={text.coverageAuditBody}
              titleClassName={headingClassName}
              bodyClassName="text-sm leading-6"
            >
              {coverageAudit.totalMissingFields > 0 ? (
                <div className="space-y-3 text-xs text-secondary-text">
                  <p className={captionClassName}>
                    {text.missingFieldsTotal}{colon}{coverageAudit.totalMissingFields}
                  </p>
                  <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
                    {coverageBuckets.map((bucket) => (
                      <div key={bucket.category} className="rounded-xl border border-[var(--theme-panel-subtle-border)] bg-base/40 px-3 py-2.5">
                        <p className={captionClassName}>
                          {coverageCategoryLabel(bucket.category)} ({bucket.entries.length})
                        </p>
                        <ul className="mt-2.5 space-y-1.5">
                          {bucket.entries.slice(0, 5).map((entry, index) => (
                            <li key={`${entry.field}-${entry.reason}-${index}`}>
                              <span className="font-medium text-foreground">{localizeReportTermLabel(entry.field, normalizedLanguage)}</span>
                              <span className="text-muted-text">{colon}{localizeReportHeadingLabel(entry.reason, normalizedLanguage)}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="text-xs text-muted-text">{text.noMissingFields}</p>
              )}
            </SupportPanel>

            <SupportPanel className="px-5 py-5 md:px-6">
              <div className="mx-auto w-full max-w-[86ch]">
                <div
                  className="home-markdown-prose prose prose-invert max-w-none
                    prose-headings:text-foreground prose-headings:font-semibold prose-headings:tracking-tight
                    prose-h1:mt-0 prose-h1:mb-4 prose-h1:text-[1.75rem] prose-h1:leading-tight
                    prose-h2:mt-8 prose-h2:mb-3 prose-h2:text-[1.35rem] prose-h2:leading-snug
                    prose-h3:mt-6 prose-h3:mb-2 prose-h3:text-[1.1rem] prose-h3:leading-snug
                    prose-h4:mt-5 prose-h4:mb-2 prose-h4:text-base prose-h4:leading-snug
                    prose-p:my-3 prose-p:leading-7 prose-p:last:mb-0
                    prose-strong:text-foreground prose-strong:font-semibold
                    prose-ul:my-3 prose-ol:my-3 prose-li:my-1 prose-li:leading-7
                    prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:before:content-none prose-code:after:content-none
                    prose-pre:my-4 prose-pre:border prose-pre:rounded-xl prose-pre:bg-[hsl(var(--elevated)/0.92)] prose-pre:p-4 prose-pre:text-xs prose-pre:leading-6
                    prose-table:my-4 prose-table:block prose-table:overflow-x-auto prose-table:rounded-xl prose-table:border prose-table:border-[var(--home-prose-border)]
                    prose-th:border prose-th:border-[var(--home-prose-border-strong)] prose-th:px-3 prose-th:py-2 prose-th:uppercase prose-th:tracking-[0.12em]
                    prose-td:border prose-td:border-[var(--home-prose-border-strong)] prose-td:px-3 prose-td:py-2 prose-td:align-top
                    prose-hr:my-6
                    prose-a:no-underline hover:prose-a:underline
                    prose-blockquote:my-4 prose-blockquote:border-l-2 prose-blockquote:border-[var(--home-prose-blockquote-border)] prose-blockquote:bg-[var(--home-prose-blockquote-bg)] prose-blockquote:px-4 prose-blockquote:py-3 prose-blockquote:text-secondary-text
                    break-words
                  "
                >
                  <Markdown remarkPlugins={[remarkGfm]}>
                    {localizedMarkdownContent}
                  </Markdown>
                </div>
              </div>
            </SupportPanel>
          </div>
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
      </div>
    </Drawer>
  );
};
