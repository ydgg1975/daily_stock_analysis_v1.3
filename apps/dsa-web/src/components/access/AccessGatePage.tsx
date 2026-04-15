import type React from 'react';
import { ArrowRight, ShieldAlert } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Card, WorkspacePageHeader } from '../common';

type ActionLink = {
  label: string;
  to: string;
};

type AccessGatePageProps = {
  eyebrow: string;
  title: string;
  description: string;
  bullets: string[];
  statusLabel?: string;
  note?: string;
  primaryAction: ActionLink;
  secondaryAction?: ActionLink;
  tertiaryAction?: ActionLink;
};

export const AccessGatePage: React.FC<AccessGatePageProps> = ({
  eyebrow,
  title,
  description,
  bullets,
  statusLabel,
  note,
  primaryAction,
  secondaryAction,
  tertiaryAction,
}) => (
  <div className="space-y-6">
    <WorkspacePageHeader
      eyebrow={eyebrow}
      title={title}
      description={description}
    />

    <Card className="max-w-3xl space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex h-12 w-12 items-center justify-center rounded-full border border-[hsl(var(--accent-warning-hsl)/0.32)] bg-[hsl(var(--accent-warning-hsl)/0.14)] text-[hsl(var(--accent-warning-hsl))]">
          <ShieldAlert className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-foreground">{title}</p>
          <p className="mt-1 text-sm text-secondary-text">{description}</p>
        </div>
        {statusLabel ? (
          <span className="inline-flex min-h-[28px] items-center rounded-full border border-[hsl(var(--accent-warning-hsl)/0.32)] bg-[hsl(var(--accent-warning-hsl)/0.14)] px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-[hsl(var(--accent-warning-hsl))]">
            {statusLabel}
          </span>
        ) : null}
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        {bullets.map((item) => (
          <div
            key={item}
            className="rounded-[var(--theme-panel-radius-md)] border border-[var(--theme-panel-subtle-border)] bg-[var(--surface-2)]/45 px-4 py-3 text-sm leading-6 text-secondary-text"
          >
            {item}
          </div>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Link
          to={primaryAction.to}
          className="inline-flex min-h-[40px] items-center justify-center gap-2 rounded-[var(--theme-button-radius)] border border-transparent bg-[var(--pill-active-bg)] px-4 text-[0.75rem] text-foreground transition-colors hover:border-[var(--border-strong)]"
        >
          <span>{primaryAction.label}</span>
          <ArrowRight className="h-4 w-4" />
        </Link>
        {secondaryAction ? (
          <Link
            to={secondaryAction.to}
            className="inline-flex min-h-[40px] items-center justify-center rounded-[var(--theme-button-radius)] border border-[var(--border-muted)] bg-[var(--pill-bg)] px-4 text-[0.75rem] text-secondary-text transition-colors hover:border-[var(--border-strong)] hover:text-foreground"
          >
            {secondaryAction.label}
          </Link>
        ) : null}
        {tertiaryAction ? (
          <Link
            to={tertiaryAction.to}
            className="inline-flex min-h-[40px] items-center justify-center rounded-[var(--theme-button-radius)] border border-transparent px-2 text-[0.75rem] text-muted-text transition-colors hover:text-foreground"
          >
            {tertiaryAction.label}
          </Link>
        ) : null}
      </div>
      {note ? <p className="text-xs leading-5 text-muted-text">{note}</p> : null}
    </Card>
  </div>
);
