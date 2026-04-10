/**
 * SpaceX live refactor: keeps the existing autocomplete submission paths and
 * follow-up/report actions intact while restyling the command surface into a
 * quieter horizontal control strip with denser desktop packing, better i18n-safe
 * button sizing, and the same follow-up/report actions preserved in place.
 */
import type React from 'react';
import { Button } from '../common';
import { StockAutocomplete } from '../StockAutocomplete';
import { useI18n } from '../../contexts/UiLanguageContext';

type CommandBarProps = {
  label: string;
  value: string;
  placeholder: string;
  disabled?: boolean;
  inputError?: string;
  onChange: (value: string) => void;
  onSubmit: (stockCode?: string, stockName?: string, selectionSource?: 'manual' | 'autocomplete') => void;
  onFollowUp: () => void;
  onViewReport: () => void;
  canFollowUp: boolean;
  canViewReport: boolean;
  analyzeText: string;
  analyzingText: string;
  followUpText: string;
  reportText: string;
};

export const CommandBar: React.FC<CommandBarProps> = ({
  label,
  value,
  placeholder,
  disabled = false,
  inputError,
  onChange,
  onSubmit,
  onFollowUp,
  onViewReport,
  canFollowUp,
  canViewReport,
  analyzeText,
  analyzingText,
  followUpText,
  reportText,
}) => {
  const { language } = useI18n();

  return (
    <section className="workspace-commandbar" aria-label={label} data-language={language}>
      <div className="workspace-commandbar__strip">
        <label className="workspace-commandbar__field">
          <span className="theme-field-label workspace-commandbar__label">{label}</span>
          <StockAutocomplete
            value={value}
            onChange={onChange}
            onSubmit={(stockCode, stockName, selectionSource) => {
              onSubmit(stockCode, stockName, selectionSource);
            }}
            placeholder={placeholder}
            disabled={disabled}
            className={inputError ? 'workspace-commandbar__input border-danger/50' : 'workspace-commandbar__input'}
          />
        </label>

        <Button
          onClick={() => onSubmit()}
          disabled={!value || disabled}
          isLoading={disabled}
          loadingText={analyzingText}
          className="workspace-commandbar__submit"
        >
          {analyzeText}
        </Button>
      </div>

      <div className="workspace-commandbar__actions">
        <Button
          variant="home-action-ai"
          size="md"
          disabled={!canFollowUp}
          onClick={onFollowUp}
          className="workspace-commandbar__action"
        >
          {followUpText}
        </Button>
        <Button
          variant="home-action-report"
          size="md"
          disabled={!canViewReport}
          onClick={onViewReport}
          className="workspace-commandbar__action"
        >
          {reportText}
        </Button>
      </div>

      {inputError ? (
        <p className="workspace-commandbar__error">{inputError}</p>
      ) : null}
    </section>
  );
};

export default CommandBar;
