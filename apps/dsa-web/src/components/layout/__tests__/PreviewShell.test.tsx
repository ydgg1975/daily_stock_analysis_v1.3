import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeAll, describe, expect, it } from 'vitest';
import { ThemeProvider } from '../../theme/ThemeProvider';
import { PreviewShell } from '../PreviewShell';

beforeAll(() => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string) => ({
      matches: query === '(prefers-color-scheme: dark)',
      media: query,
      onchange: null,
      addListener: () => undefined,
      removeListener: () => undefined,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      dispatchEvent: () => false,
    }),
  });
});

afterEach(() => {
  window.innerWidth = 1280;
  window.dispatchEvent(new Event('resize'));
});

describe('PreviewShell', () => {
  it('renders a single desktop theme control in the preview rail', () => {
    render(
      <MemoryRouter initialEntries={['/__preview/report']}>
        <ThemeProvider>
          <PreviewShell>
            <div>preview content</div>
          </PreviewShell>
        </ThemeProvider>
      </MemoryRouter>,
    );

    expect(screen.getByTestId('preview-shell')).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: '切换主题' })).toHaveLength(1);
    expect(screen.queryByRole('button', { name: '打开导航菜单' })).not.toBeInTheDocument();
  });

  it('keeps the mobile preview top bar limited to the menu trigger and moves theme control into the drawer', async () => {
    window.innerWidth = 390;

    render(
      <MemoryRouter initialEntries={['/__preview/report']}>
        <ThemeProvider>
          <PreviewShell>
            <div>preview content</div>
          </PreviewShell>
        </ThemeProvider>
      </MemoryRouter>,
    );

    expect(screen.getByRole('button', { name: '打开导航菜单' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '切换主题' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '打开导航菜单' }));

    expect(await screen.findByRole('button', { name: '切换主题' })).toBeInTheDocument();
  });
});
