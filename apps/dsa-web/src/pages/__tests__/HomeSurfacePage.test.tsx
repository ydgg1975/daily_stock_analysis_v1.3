import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import HomeSurfacePage from '../HomeSurfacePage';

const { useProductSurfaceMock } = vi.hoisted(() => ({
  useProductSurfaceMock: vi.fn(),
}));

vi.mock('../../hooks/useProductSurface', () => ({
  useProductSurface: () => useProductSurfaceMock(),
}));

vi.mock('../GuestHomePage', () => ({
  default: () => <div>guest home page</div>,
}));

vi.mock('../HomePage', () => ({
  default: () => <div>full home page</div>,
}));

describe('HomeSurfacePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the guest homepage when the current surface role is guest', () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: true });
    render(<HomeSurfacePage />);
    expect(screen.getByText('guest home page')).toBeInTheDocument();
  });

  it('renders the full homepage for signed-in users', () => {
    useProductSurfaceMock.mockReturnValue({ isGuest: false });
    render(<HomeSurfacePage />);
    expect(screen.getByText('full home page')).toBeInTheDocument();
  });
});
