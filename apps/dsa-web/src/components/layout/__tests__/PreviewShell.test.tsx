import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeAll, describe, expect, it } from 'vitest';
import { translate } from '../../../i18n/core';
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
  it('renders the localized desktop preview action and no mobile menu', () => {
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
    expect(screen.getByRole('button', { name: translate('zh', 'preview.shellAction') })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: translate('zh', 'shell.openMenu') })).not.toBeInTheDocument();
  });

  it('shows localized preview rail content in the mobile drawer', async () => {
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

    expect(screen.getByRole('button', { name: translate('zh', 'shell.openMenu') })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: translate('zh', 'preview.shellAction') })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'shell.openMenu') }));

    expect(await screen.findByText(translate('zh', 'preview.shellTitle'))).toBeInTheDocument();
  });
});
