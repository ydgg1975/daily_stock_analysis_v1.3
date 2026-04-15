import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { AccessGatePage } from '../AccessGatePage';

describe('AccessGatePage', () => {
  it('renders status, actions, and supporting note for locked surfaces', () => {
    render(
      <MemoryRouter>
        <AccessGatePage
          eyebrow="Registered User Only"
          title="Sign in to continue"
          description="This workflow requires a real account."
          bullets={[
            'Saved history belongs to authenticated users.',
            'Guest mode stays in preview only.',
          ]}
          statusLabel="Guest Preview Only"
          note="After sign-in, you will return to this workflow automatically."
          primaryAction={{ label: 'Sign in', to: '/login?redirect=%2Fchat' }}
          secondaryAction={{ label: 'Create account', to: '/login?mode=create&redirect=%2Fchat' }}
          tertiaryAction={{ label: 'Back home', to: '/' }}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText('Guest Preview Only')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login?redirect=%2Fchat');
    expect(screen.getByRole('link', { name: 'Create account' })).toHaveAttribute('href', '/login?mode=create&redirect=%2Fchat');
    expect(screen.getByRole('link', { name: 'Back home' })).toHaveAttribute('href', '/');
    expect(screen.getByText('After sign-in, you will return to this workflow automatically.')).toBeInTheDocument();
  });
});
