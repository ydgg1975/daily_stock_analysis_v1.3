import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { DashboardStateBlock } from '../DashboardStateBlock';

describe('DashboardStateBlock', () => {
  it('renders the title as a paragraph by default', () => {
    const { container } = render(<DashboardStateBlock title="kaishifenxi" description="chakantishiwenan" />);

    const title = screen.getByText('kaishifenxi');
    expect(title.tagName).toBe('P');
    expect(container.querySelector('h3')).toBeNull();
  });

  it('renders the title with the requested heading level', () => {
    render(<DashboardStateBlock title="kaishifenxi" titleAs="h3" description="chakantishiwenan" />);

    expect(screen.getByRole('heading', { name: 'kaishifenxi', level: 3 })).toBeInTheDocument();
  });

  it('keeps icon, description, action, and loading behaviors intact', () => {
    const { rerender } = render(
      <DashboardStateBlock
        title="kaishifenxi"
        description="shurugupiaodaimajinxingfenxi"
        icon={<span data-testid="icon">icon</span>}
        action={<button type="button">lijikaishi</button>}
      />,
    );

    expect(screen.getByTestId('icon')).toBeInTheDocument();
    expect(screen.getByText('shurugupiaodaimajinxingfenxi')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'lijikaishi' })).toBeInTheDocument();

    rerender(
      <DashboardStateBlock
        title="kaishifenxi"
        titleAs="h3"
        description="shurugupiaodaimajinxingfenxi"
        loading
      />,
    );

    expect(screen.getByRole('heading', { name: 'kaishifenxi', level: 3 })).toBeInTheDocument();
    expect(screen.getByText('shurugupiaodaimajinxingfenxi')).toBeInTheDocument();
    expect(document.querySelector('.home-spinner')).not.toBeNull();
    expect(screen.queryByTestId('icon')).not.toBeInTheDocument();
  });
});
