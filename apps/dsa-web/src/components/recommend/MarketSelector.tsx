import React from 'react';
import { Checkbox } from '../common';

const MARKET_OPTIONS = [
  { value: 'a_share', label: 'A 股' },
  { value: 'hk', label: '港股' },
  { value: 'us', label: '美股' },
];

interface MarketSelectorProps {
  selected: string[];
  onChange: (markets: string[]) => void;
}

export const MarketSelector: React.FC<MarketSelectorProps> = ({ selected, onChange }) => {
  const toggle = (value: string) => {
    if (selected.includes(value)) {
      onChange(selected.filter((m) => m !== value));
    } else {
      onChange([...selected, value]);
    }
  };

  return (
    <div className="flex flex-wrap gap-4">
      {MARKET_OPTIONS.map((opt) => (
        <Checkbox
          key={opt.value}
          label={opt.label}
          checked={selected.includes(opt.value)}
          onChange={() => toggle(opt.value)}
        />
      ))}
    </div>
  );
};
