import type React from 'react';
import GuestScannerPage from './GuestScannerPage';
import ScannerPage from './ScannerPage';
import UserScannerPage from './UserScannerPage';
import { useProductSurface } from '../hooks/useProductSurface';

const ScannerSurfacePage: React.FC = () => {
  const { isGuest, isAdminMode } = useProductSurface();

  if (isGuest) {
    return <GuestScannerPage />;
  }

  return isAdminMode ? <ScannerPage /> : <UserScannerPage />;
};

export default ScannerSurfacePage;
