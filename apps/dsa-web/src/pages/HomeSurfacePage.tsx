import type React from 'react';
import GuestHomePage from './GuestHomePage';
import HomePage from './HomePage';
import { useProductSurface } from '../hooks/useProductSurface';

const HomeSurfacePage: React.FC = () => {
  const { isGuest } = useProductSurface();
  return isGuest ? <GuestHomePage /> : <HomePage />;
};

export default HomeSurfacePage;
