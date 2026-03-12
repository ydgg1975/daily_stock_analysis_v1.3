import type React from 'react';
import { cn } from '../../utils/cn';

interface StatCardProps {
  /** 统计指标标签（如"总收益率"） */
  label: string;
  /** 统计数值（支持数字、百分比等） */
  value: React.ReactNode;
  /** 辅助说明文字（如"较上月 +5%"） */
  hint?: React.ReactNode;
  /** 右侧图标 */
  icon?: React.ReactNode;
  /** 色调主题（影响边框颜色） */
  tone?: 'default' | 'primary' | 'success' | 'warning' | 'danger';
  /** 额外的 className */
  className?: string;
}

const toneStyles = {
  default: 'border-white/8',
  primary: 'border-cyan/18',
  success: 'border-success/18',
  warning: 'border-warning/18',
  danger: 'border-danger/18',
};

export const StatCard: React.FC<StatCardProps> = ({
  label,
  value,
  hint,
  icon,
  tone = 'default',
  className = '',
}) => {
  return (
    <div className={cn('rounded-2xl border bg-card/75 p-4 shadow-soft-card', toneStyles[tone], className)}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.22em] text-secondary">{label}</p>
          <div className="mt-2 text-2xl font-semibold text-white">{value}</div>
          {hint ? <div className="mt-2 text-sm text-secondary">{hint}</div> : null}
        </div>
        {icon ? <div className="text-cyan">{icon}</div> : null}
      </div>
    </div>
  );
};
