import type React from 'react';
import { useEffect, useMemo } from 'react';
import { WorkspacePageHeader } from '../components/common';
import { StandardReportPanel } from '../components/report';
import { previewChartFixtures, previewReport } from '../dev/reportPreviewFixture';
import { normalizeFrontendReportContract } from '../api/reportNormalizer';

const PreviewReportPage: React.FC = () => {
  const normalizedPreviewReport = useMemo(
    () => normalizeFrontendReportContract(previewReport),
    [],
  );

  useEffect(() => {
    document.title = 'Report Preview - WolfyStock';
  }, []);

  return (
    <div className="workspace-page workspace-page--preview" data-testid="preview-report-page">
      <WorkspacePageHeader
        eyebrow="WolfyStock Preview Workspace"
        title="Report preview"
        description="开发态响应式预览页，用于校验桌面与移动端的报告层级、图表结构和主题表现。"
      />

      <StandardReportPanel report={normalizedPreviewReport} chartFixtures={previewChartFixtures} />
    </div>
  );
};

export default PreviewReportPage;
