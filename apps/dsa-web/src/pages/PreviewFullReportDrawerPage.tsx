import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import { WorkspacePageHeader } from '../components/common';
import { ReportMarkdown } from '../components/report';
import { previewReport } from '../dev/reportPreviewFixture';
import { normalizeFrontendReportContract } from '../api/reportNormalizer';
import type { ReportLanguage } from '../types/analysis';
import { useI18n } from '../contexts/UiLanguageContext';

const previewMarkdownZh = `# NVIDIA（NVDA）完整研究报告

## 一、结论摘要
当前建议维持“等待回踩确认后分批试仓”的执行框架。核心判断来自价格结构仍偏多，但短线动量与上方压力位尚未完成再平衡。

## 二、执行层（可操作）
### 2.1 当前动作
- 优先观察回踩 MA20 附近是否出现承接。
- 若成交量放大但价格未失守关键支撑，可考虑首笔试仓。
- 若价格快速跌破支撑并放量，暂停执行，进入防守模式。

### 2.2 新开仓计划
1. 理想买入区间：120-121。
2. 次优买入点：118。
3. 止损位：115。
4. 目标区间：132-138。

## 三、证据层（行情与结构）
### 3.1 市场结构
当前 MA5/10/20/60 结构仍支持中期趋势框架，但短线斜率边际转弱，说明交易层面仍需等待回踩确认而非追高。

### 3.2 催化与风险
- 利好：数据中心需求回暖、AI 订单延续。
- 风险：估值偏高、前高压力仍在。
- 观察：若新增公司级催化不足，短线更依赖技术结构确认。

### 3.3 数据证据表
| 字段 | 数值 | 口径 |
| --- | --- | --- |
| Analysis Price | 125.30 | Intraday snapshot |
| Change % | 1.87% | Session vs Prev Close |
| MA20 | 120.99 | FMP API |
| RSI14 | 56.78 | FMP API |
| VWAP | NA（字段待接入） | Coverage gap |
| 盘后成交额 | NA（会话不适用） | Session rule |

## 四、覆盖与审计
### 4.1 缺失字段说明
- VWAP：NA（字段待接入）
- Beta：NA（接口未返回）
- 盘后成交额：NA（会话不适用）

### 4.2 覆盖审计备注
> 该报告保留所有缺失字段与原因归类，用于后续 API 接入与数据源排期，不作为删除内容的依据。

## 五、附录
### 5.1 方法说明
标准技术指标优先采用 API 原始值；冲突字段按统一口径重算并保留备注。

### 5.2 风险提示
本报告用于研究讨论，不构成投资建议。`;

const previewMarkdownEn = `# NVIDIA (NVDA) Full Research Memo

## 1. Executive Summary
The current stance remains "wait for pullback confirmation, then scale in gradually." The trend structure is still constructive, while short-term momentum and overhead resistance are not fully resolved.

## 2. Execution Layer
### 2.1 Immediate Actions
- Watch for demand response near MA20.
- Consider the first probe position only if support holds with healthy volume.
- If support breaks with expanding volume, pause execution and switch to defense.

### 2.2 New Position Plan
1. Ideal entry range: 120-121.
2. Secondary entry: 118.
3. Stop loss: 115.
4. Target zone: 132-138.

## 3. Evidence Layer
### 3.1 Structure
MA5/10/20/60 still supports the medium-term trend framework, but short-term slope is flattening. This supports a pullback-first approach rather than chasing strength.

### 3.2 Catalysts and Risks
- Bullish: data-center demand recovery, sustained AI orders.
- Risks: elevated valuation, overhead resistance near previous highs.
- Watch item: in the absence of new company-level catalysts, setup quality depends more on technical confirmation.

### 3.3 Data Table
| Field | Value | Basis |
| --- | --- | --- |
| Analysis Price | 125.30 | Intraday snapshot |
| Change % | 1.87% | Session vs Prev Close |
| MA20 | 120.99 | FMP API |
| RSI14 | 56.78 | FMP API |
| VWAP | NA (not integrated yet) | Coverage gap |
| After-hours turnover | NA (not applicable in this session) | Session rule |

## 4. Coverage and Audit
### 4.1 Missing Fields
- VWAP: NA (not integrated yet)
- Beta: NA (integrated but unavailable)
- After-hours turnover: NA (not applicable in this session)

### 4.2 Audit Notes
> Missing fields and classified reasons are intentionally preserved for API integration planning and traceability.

## 5. Appendix
### 5.1 Method Notes
Technical indicators prioritize original API values. Conflicting fields are normalized with explicit basis notes.

### 5.2 Risk Notice
This memo is for research discussion and does not constitute investment advice.`;

const PreviewFullReportDrawerPage: React.FC = () => {
  const { t } = useI18n();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [language, setLanguage] = useState<ReportLanguage>('zh');
  const normalizedPreviewReport = useMemo(
    () => normalizeFrontendReportContract(previewReport),
    [],
  );

  useEffect(() => {
    document.title = `${t('preview.fullDrawerTitle')} - WolfyStock`;
  }, [t]);

  const content = language === 'en' ? previewMarkdownEn : previewMarkdownZh;
  const stockName = language === 'en' ? 'NVIDIA' : '英伟达';

  return (
    <div className="workspace-page workspace-page--preview" data-testid="preview-full-report-page">
      <WorkspacePageHeader
        eyebrow={t('preview.workspaceEyebrow')}
        title={t('preview.fullDrawerTitle')}
        description={t('preview.fullDrawerDesc')}
      />

      <div className="theme-panel-solid rounded-[1.25rem] px-4 py-4 md:px-5">
        <p className="text-[11px] uppercase tracking-[0.16em] text-muted-text">{t('preview.fullModeTitle')}</p>
        <p className="mt-2 text-sm leading-6 text-secondary-text">
          {t('preview.fullModeBody')}
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            className="home-surface-button rounded-lg px-4 py-2 text-sm"
            onClick={() => {
              setLanguage('zh');
              setDrawerOpen(true);
            }}
          >
            {t('preview.openChinese')}
          </button>
          <button
            type="button"
            className="home-surface-button rounded-lg px-4 py-2 text-sm"
            onClick={() => {
              setLanguage('en');
              setDrawerOpen(true);
            }}
          >
            {t('preview.openEnglish')}
          </button>
        </div>
      </div>

      {drawerOpen ? (
        <ReportMarkdown
          recordId={-1}
          stockName={stockName}
          stockCode="NVDA"
          onClose={() => setDrawerOpen(false)}
          reportLanguage={language}
          standardReport={normalizedPreviewReport.details?.standardReport}
          initialContent={content}
        />
      ) : null}
    </div>
  );
};

export default PreviewFullReportDrawerPage;
