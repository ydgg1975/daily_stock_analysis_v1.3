import { fireEvent, render, screen } from '@testing-library/react';
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
  it('opens the theme menu and shows all theme modes', async () => {
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>
    );

    fireEvent.click(screen.getByRole('button', { name: '테마 전환' }));

    expect(await screen.findByRole('menu', { name: '테마 모드' })).toBeInTheDocument();
    expect(screen.getByRole('menuitemradio', { name: '밝은 테마' })).toBeInTheDocument();
    expect(screen.getByRole('menuitemradio', { name: '어두운 테마' })).toBeInTheDocument();
    expect(screen.getByRole('menuitemradio', { name: '시스템 설정' })).toBeInTheDocument();
  });
});
