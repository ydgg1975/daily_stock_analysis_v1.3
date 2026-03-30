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
        <div className="app-boot-splash__logo-wrap" aria-hidden="true">
          <span className="app-boot-splash__halo app-boot-splash__halo--outer" />
          <span className="app-boot-splash__halo app-boot-splash__halo--inner" />
          <img
            src="/image.png"
            alt="WolfyStock"
            className="app-boot-splash__logo"
            decoding="async"
            loading="eager"
          />
          <span className="app-boot-splash__scan" />
        </div>

        <p className="app-boot-splash__text">{text}</p>
        {subtext ? <p className="app-boot-splash__subtext">{subtext}</p> : null}

        <div className="app-boot-splash__progress" aria-hidden="true">
          <span className="app-boot-splash__progress-bar" />
        </div>
      </div>
    </div>
  );
};
