import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { translate } from '../../i18n/core';
import PreviewReportPage from '../PreviewReportPage';

vi.mock('../../components/report', () => ({
  StandardReportPanel: () => <div data-testid="standard-report-panel">standard panel</div>,
}));

describe('PreviewReportPage', () => {
  it('renders preview workspace and report panel', () => {
    render(<PreviewReportPage />);

    expect(screen.getByTestId('preview-report-page')).toBeInTheDocument();
    expect(screen.getByText(translate('zh', 'preview.reportTitle'))).toBeInTheDocument();
    expect(screen.getByTestId('standard-report-panel')).toBeInTheDocument();
  });
});
