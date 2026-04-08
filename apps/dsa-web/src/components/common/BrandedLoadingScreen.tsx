import type React from 'react';

interface BrandedLoadingScreenProps {
  fading?: boolean;
  text?: string;
  subtext?: string;
}

export const BrandedLoadingScreen: React.FC<BrandedLoadingScreenProps> = ({
  fading = false,
  text = 'Loading WolfyStock...',
  subtext,
}) => {
  return (
    <div
      className={`app-boot-splash${fading ? ' is-fading' : ''}`}
      role="status"
      aria-live="polite"
      aria-label={text}
    >
      <div className="app-boot-splash__inner">
        <p className="app-boot-splash__eyebrow">Research Workspace</p>
        <p className="app-boot-splash__wordmark">WolfyStock</p>

        <p className="app-boot-splash__text">{text}</p>
        {subtext ? <p className="app-boot-splash__subtext">{subtext}</p> : null}

        <div className="app-boot-splash__progress" aria-hidden="true">
          <span className="app-boot-splash__progress-bar" />
        </div>
      </div>
    </div>
  );
};
