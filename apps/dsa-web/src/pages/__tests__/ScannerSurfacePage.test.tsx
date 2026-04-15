import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import ScannerSurfacePage from '../ScannerSurfacePage';

const { useProductSurfaceMock } = vi.hoisted(() => ({
  useProductSurfaceMock: vi.fn(),
}));

vi.mock('../../hooks/useProductSurface', () => ({
  useProductSurface: () => useProductSurfaceMock(),
}));

vi.mock('../GuestScannerPage', () => ({
  default: () => <div>guest scanner page</div>,
}));

vi.mock('../UserScannerPage', () => ({
  default: () => <div>user scanner page</div>,
}));

vi.mock('../ScannerPage', () => ({
  default: () => <div>admin scanner page</div>,
}));

describe('ScannerSurfacePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders guest teaser for guests', () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: true, isAdminMode: false });
    render(<ScannerSurfacePage />);
    expect(screen.getByText('guest scanner page')).toBeInTheDocument();
  });

  it('renders user scanner surface for normal signed-in users', () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false, isAdminMode: false });
    render(<ScannerSurfacePage />);
    expect(screen.getByText('user scanner page')).toBeInTheDocument();
  });

  it('renders admin scanner surface only when admin mode is enabled', () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false, isAdminMode: true });
    render(<ScannerSurfacePage />);
    expect(screen.getByText('admin scanner page')).toBeInTheDocument();
  });
});
