import React from 'react';
import { Input } from '../common';

interface PriceRangeInputProps {
  min: string;
  max: string;
  onMinChange: (v: string) => void;
  onMaxChange: (v: string) => void;
}

export const PriceRangeInput: React.FC<PriceRangeInputProps> = ({
  min,
  max,
  onMinChange,
  onMaxChange,
}) => {
  return (
    <div className="flex items-center gap-3">
      <Input
        type="number"
        placeholder="最低价"
        value={min}
        onChange={(e) => onMinChange(e.target.value)}
        className="w-32"
        min={0}
        step="0.01"
      />
      <span className="text-secondary-text">~</span>
      <Input
        type="number"
        placeholder="最高价"
        value={max}
        onChange={(e) => onMaxChange(e.target.value)}
        className="w-32"
        min={0}
        step="0.01"
      />
    </div>
  );
};
