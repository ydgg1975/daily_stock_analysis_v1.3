import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import GuestScannerPage from '../GuestScannerPage';

vi.mock('../../contexts/UiLanguageContext', () => ({
  useI18n: () => ({
    language: 'zh',
  }),
}));

describe('GuestScannerPage', () => {
  it('shows sign-in and create-account CTAs for the guest scanner teaser', () => {
    render(
      <MemoryRouter>
        <GuestScannerPage />
      </MemoryRouter>,
    );

    expect(screen.getByRole('link', { name: '登录后运行扫描器' })).toHaveAttribute('href', '/login?redirect=%2Fscanner');
    expect(screen.getByRole('link', { name: '创建账户' })).toHaveAttribute('href', '/login?mode=create&redirect=%2Fscanner');
    expect(screen.getByText('手动运行')).toBeInTheDocument();
    expect(screen.getByText('保存观察名单')).toBeInTheDocument();
  });
});
