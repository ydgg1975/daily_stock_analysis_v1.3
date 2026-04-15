import type React from 'react';
import type { LucideIcon } from 'lucide-react';
import { LockKeyhole } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Card } from '../common';

type LockedFeatureCardProps = {
  icon: LucideIcon;
  title: string;
  body: string;
  lockedLabel?: string;
  ctaLabel?: string;
  ctaTo?: string;
};

export const LockedFeatureCard: React.FC<LockedFeatureCardProps> = ({
  icon: Icon,
  title,
  body,
  lockedLabel = 'Locked',
  ctaLabel,
  ctaTo,
}) => (
  <Card className="relative overflow-hidden border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/45">
    <div className="absolute inset-0 bg-[linear-gradient(135deg,rgba(255,255,255,0.03),rgba(255,255,255,0.01))]" aria-hidden="true" />
    <div className="absolute inset-x-5 bottom-4 h-10 rounded-full bg-[rgba(255,255,255,0.22)] blur-2xl" aria-hidden="true" />
    <div className="absolute inset-x-4 top-[4.25rem] h-px bg-[linear-gradient(90deg,transparent,rgba(255,255,255,0.25),transparent)]" aria-hidden="true" />
    <div className="absolute inset-[1.15rem] rounded-[1.1rem] border border-white/10 bg-[rgba(255,255,255,0.03)] backdrop-blur-[2px]" aria-hidden="true" />

    <div className="relative z-[1] space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-full border border-white/10 bg-white/6 text-foreground">
          <Icon className="h-5 w-5" />
        </div>
        <span className="inline-flex items-center gap-1 rounded-full border border-[hsl(var(--accent-warning-hsl)/0.35)] bg-[hsl(var(--accent-warning-hsl)/0.16)] px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-[hsl(var(--accent-warning-hsl))]">
          <LockKeyhole className="h-3 w-3" />
          {lockedLabel}
        </span>
      </div>

      <div>
        <h3 className="text-base font-semibold text-foreground">{title}</h3>
        <p className="mt-2 text-sm leading-6 text-secondary-text">{body}</p>
      </div>

      {ctaLabel && ctaTo ? (
        <Link
          to={ctaTo}
          className="inline-flex min-h-[34px] items-center justify-center rounded-[var(--theme-button-radius)] border border-[var(--border-muted)] bg-[var(--pill-bg)] px-3 text-[0.72rem] text-secondary-text transition-colors hover:border-[var(--border-strong)] hover:text-foreground"
        >
          {ctaLabel}
        </Link>
      ) : null}
    </div>
  </Card>
);
