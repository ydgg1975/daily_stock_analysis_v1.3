import type React from 'react';
import type { MarketType } from '../../types/market';

interface MarketSelectorProps {
  value: MarketType;
  onChange: (market: MarketType) => void;
  disabled?: boolean;
  className?: string;
}

export const MarketSelector: React.FC<MarketSelectorProps> = ({
  value,
  onChange,
  disabled = false,
  className = '',
}) => {
  const options: { value: MarketType; label: string; icon: string }[] = [
    { value: 'cn', label: 'A 股', icon: '🇨🇳' },
    { value: 'us', label: '美股', icon: '🇺🇸' },
    { value: 'both', label: '全部', icon: '🌍' },
  ];

  return (
    <div className={`inline-flex items-center gap-1 p-1 rounded-lg bg-muted/50 ${className}`}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          disabled={disabled}
          onClick={() => onChange(option.value)}
          className={`
            inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium
            transition-all duration-150
            ${
              value === option.value
                ? 'bg-card text-foreground shadow-sm'
                : 'text-muted-text hover:text-foreground hover:bg-hover'
            }
            disabled:opacity-50 disabled:cursor-not-allowed
          `}
        >
          <span className="text-base">{option.icon}</span>
          <span>{option.label}</span>
        </button>
      ))}
    </div>
  );
};