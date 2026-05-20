import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { DashboardStateBlock } from '../DashboardStateBlock';

describe('DashboardStateBlock', () => {
  it('renders the title as a paragraph by default', () => {
    const { container } = render(<DashboardStateBlock title="분석 시작" description="안내 문구를 확인합니다" />);

    const title = screen.getByText('분석 시작');
    expect(title.tagName).toBe('P');
    expect(container.querySelector('h3')).toBeNull();
  });

  it('renders the title with the requested heading level', () => {
    render(<DashboardStateBlock title="분석 시작" titleAs="h3" description="안내 문구를 확인합니다" />);

    expect(screen.getByRole('heading', { name: '분석 시작', level: 3 })).toBeInTheDocument();
  });

  it('keeps icon, description, action, and loading behaviors intact', () => {
    const { rerender } = render(
      <DashboardStateBlock
        title="분석 시작"
        description="종목 코드를 입력해 분석합니다"
        icon={<span data-testid="icon">icon</span>}
        action={<button type="button">바로 시작</button>}
      />,
    );

    expect(screen.getByTestId('icon')).toBeInTheDocument();
    expect(screen.getByText('종목 코드를 입력해 분석합니다')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '바로 시작' })).toBeInTheDocument();

    rerender(
      <DashboardStateBlock
        title="분석 시작"
        titleAs="h3"
        description="종목 코드를 입력해 분석합니다"
        loading
      />,
    );

    expect(screen.getByRole('heading', { name: '분석 시작', level: 3 })).toBeInTheDocument();
    expect(screen.getByText('종목 코드를 입력해 분석합니다')).toBeInTheDocument();
    expect(document.querySelector('.home-spinner')).not.toBeNull();
    expect(screen.queryByTestId('icon')).not.toBeInTheDocument();
  });
});
