import type React from 'react';
import { useState, useEffect, useRef } from 'react';
import { getSentimentLabel, type ReportLanguage } from '../../types/analysis';
import { cn } from '../../utils/cn';
import { normalizeReportLanguage, getReportText } from '../../utils/reportLanguage';

interface ScoreGaugeProps {
  score: number;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
  className?: string;
  language?: ReportLanguage;
}

/**
 * Sentiment score gauge aligned to the shared product design system.
 */
export const ScoreGauge: React.FC<ScoreGaugeProps> = ({
  score,
  size = 'md',
  showLabel = true,
  className = '',
  language = 'zh',
}) => {
  // Animated score state.
  const [animatedScore, setAnimatedScore] = useState(0);
  const [displayScore, setDisplayScore] = useState(0);
  const animationRef = useRef<number | null>(null);
  const prevScoreRef = useRef(0);

  // Animate transitions between score updates.
  useEffect(() => {
    const startScore = prevScoreRef.current;
    const endScore = score;
    const duration = 1000; // Animation duration in ms.
    const startTime = performance.now();

    const animate = (currentTime: number) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);

      // Use an ease-out cubic curve for a smoother finish.
      const easeOut = 1 - Math.pow(1 - progress, 3);

      const currentScore = startScore + (endScore - startScore) * easeOut;
      setAnimatedScore(currentScore);
      setDisplayScore(Math.round(currentScore));

      if (progress < 1) {
        animationRef.current = requestAnimationFrame(animate);
      } else {
        prevScoreRef.current = endScore;
      }
    };

    animationRef.current = requestAnimationFrame(animate);

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [score]);

  const reportLanguage = normalizeReportLanguage(language);
  const text = getReportText(reportLanguage);
  const label = getSentimentLabel(score, reportLanguage);

  // Size configuration for each gauge variant.
  const sizeConfig = {
    sm: { width: 104, stroke: 8, fontSize: 'text-[1.9rem]', labelSize: 'text-xs' },
    md: { width: 136, stroke: 9, fontSize: 'text-[2.4rem]', labelSize: 'text-sm' },
    lg: { width: 168, stroke: 10, fontSize: 'text-[2.9rem]', labelSize: 'text-[0.95rem]' },
  };

  const { width, stroke, fontSize, labelSize } = sizeConfig[size];
  const radius = (width - stroke) / 2;
  const circumference = 2 * Math.PI * radius;

  // Start from the top and render a 270-degree arc.
  const arcLength = circumference * 0.75;
  const progress = (animatedScore / 100) * arcLength;

  const sentimentConfig = {
    greed: {
      color: 'var(--theme-chart-bull)',
      ring: 'rgba(29, 129, 76, 0.12)',
    },
    neutral: {
      color: 'var(--cohere-blue)',
      ring: 'rgba(24, 99, 220, 0.12)',
    },
    fear: {
      color: 'var(--theme-chart-bear)',
      ring: 'rgba(164, 54, 54, 0.12)',
    },
  };

  // Map score to sentiment key
  const getSentimentKey = (s: number): 'greed' | 'neutral' | 'fear' => {
    if (s >= 60) return 'greed';
    if (s >= 40) return 'neutral';
    return 'fear';
  };

  const sentimentKey = getSentimentKey(animatedScore);
  const colors = sentimentConfig[sentimentKey];
  const trackColor = 'var(--theme-table-border)';

  return (
    <div className={cn('flex flex-col items-center', className)}>
      {showLabel && (
        <span className="label-uppercase mb-4 text-secondary-text">
          {text.fearGreedIndex}
        </span>
      )}

      <div className="relative" style={{ width, height: width }}>
        <svg className="gauge-ring overflow-visible" width={width} height={width}>
          {/* Background track */}
          <circle
            cx={width / 2}
            cy={width / 2}
            r={radius}
            fill="none"
            stroke={trackColor}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${arcLength} ${circumference}`}
            transform={`rotate(135 ${width / 2} ${width / 2})`}
          />

          {/* Quiet sentiment ring */}
          <circle
            cx={width / 2}
            cy={width / 2}
            r={radius}
            fill="none"
            stroke={colors.ring}
            strokeWidth={stroke + 4}
            strokeLinecap="round"
            strokeDasharray={`${progress} ${circumference}`}
            transform={`rotate(135 ${width / 2} ${width / 2})`}
            opacity="1"
          />

          {/* Progress arc */}
          <circle
            cx={width / 2}
            cy={width / 2}
            r={radius}
            fill="none"
            stroke={colors.color}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={`${progress} ${circumference}`}
            transform={`rotate(135 ${width / 2} ${width / 2})`}
          />
        </svg>

        {/* Center value */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span
            className={cn('text-foreground', fontSize)}
            style={{ fontFamily: 'var(--theme-heading-font)', fontWeight: 400, letterSpacing: '-0.04em' }}
          >
            {displayScore}
          </span>
          {showLabel && (
            <span
              className={cn(labelSize, 'mt-1 font-normal tracking-[-0.01em]')}
              style={{ color: colors.color }}
            >
              {label}
            </span>
          )}
        </div>
      </div>
    </div>
  );
};
