import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeAll, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '../ThemeProvider';
import { ThemeToggle } from '../ThemeToggle';

beforeAll(() => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: query === '(prefers-color-scheme: dark)',
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
});

describe('ThemeToggle', () => {
  it('opens the theme menu and keeps the single workspace shell preset active', async () => {
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>
    );

    fireEvent.click(screen.getByRole('button', { name: '切换主题' }));

    expect(await screen.findByRole('menu', { name: '主题模式' })).toBeInTheDocument();
    const spacexOption = screen.getByRole('menuitemradio', { name: /Workspace Shell/ });
    expect(spacexOption).toBeInTheDocument();
    expect(screen.getAllByRole('menuitemradio')).toHaveLength(1);

    fireEvent.click(spacexOption);

    await waitFor(() => {
      expect(document.documentElement.dataset.theme).toBe('spacex');
      expect(document.body.dataset.theme).toBe('spacex');
      expect(window.localStorage.getItem('dsa-theme-style')).toBe('spacex');
    });
  });

  it('closes popover on outside click and Escape', async () => {
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>
    );

    fireEvent.click(screen.getByRole('button', { name: '切换主题' }));
    expect(await screen.findByRole('menu', { name: '主题模式' })).toBeInTheDocument();

    fireEvent.mouseDown(document.body);
    await waitFor(() => {
      expect(screen.queryByRole('menu', { name: '主题模式' })).not.toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: '切换主题' }));
    expect(await screen.findByRole('menu', { name: '主题模式' })).toBeInTheDocument();
    fireEvent.keyDown(document, { key: 'Escape' });

    await waitFor(() => {
      expect(screen.queryByRole('menu', { name: '主题模式' })).not.toBeInTheDocument();
    });
  });
});
