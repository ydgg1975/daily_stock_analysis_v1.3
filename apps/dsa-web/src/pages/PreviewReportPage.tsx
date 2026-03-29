import type React from 'react';
import { StandardReportPanel } from '../components/report';
import { previewChartFixtures, previewReport } from '../dev/reportPreviewFixture';

const PreviewReportPage: React.FC = () => {
  return (
    <div className="workspace-page">
      <header className="workspace-header-panel">
        <p className="text-[11px] uppercase tracking-[0.18em] text-muted-text">DSA Preview Workspace</p>
        <h1 className="mt-2 text-xl font-semibold tracking-tight text-foreground md:text-2xl">Report preview</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-secondary-text">
          开发态响应式预览页，用于校验桌面与移动端的报告层级、图表结构和主题表现。
        </p>
      </header>

      <StandardReportPanel report={previewReport} chartFixtures={previewChartFixtures} />
    </div>
  );
};

export default PreviewReportPage;
