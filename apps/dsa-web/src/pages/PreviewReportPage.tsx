import type React from 'react';
import { useEffect, useMemo } from 'react';
import { WorkspacePageHeader } from '../components/common';
import { StandardReportPanel } from '../components/report';
import { previewChartFixtures, previewReport } from '../dev/reportPreviewFixture';
import { normalizeFrontendReportContract } from '../api/reportNormalizer';
import { useI18n } from '../contexts/UiLanguageContext';

const PreviewReportPage: React.FC = () => {
  const { t } = useI18n();
  const normalizedPreviewReport = useMemo(
    () => normalizeFrontendReportContract(previewReport),
    [],
  );

  useEffect(() => {
    document.title = `${t('preview.reportTitle')} - WolfyStock`;
  }, [t]);

  return (
    <div className="workspace-page workspace-page--preview" data-testid="preview-report-page">
      <WorkspacePageHeader
        eyebrow={t('preview.workspaceEyebrow')}
        title={t('preview.reportTitle')}
        description={t('preview.reportDesc')}
      />

      <StandardReportPanel report={normalizedPreviewReport} chartFixtures={previewChartFixtures} />
    </div>
  );
};

export default PreviewReportPage;
