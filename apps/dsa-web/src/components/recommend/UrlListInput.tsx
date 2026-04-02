import React from 'react';
import { Input, Button } from '../common';
import { Plus, X } from 'lucide-react';

interface UrlListInputProps {
  urls: string[];
  onChange: (urls: string[]) => void;
  max?: number;
}

export const UrlListInput: React.FC<UrlListInputProps> = ({ urls, onChange, max = 10 }) => {
  const addUrl = () => {
    if (urls.length < max) {
      onChange([...urls, '']);
    }
  };

  const removeUrl = (index: number) => {
    onChange(urls.filter((_, i) => i !== index));
  };

  const updateUrl = (index: number, value: string) => {
    const updated = [...urls];
    updated[index] = value;
    onChange(updated);
  };

  const handlePaste = (index: number, e: React.ClipboardEvent<HTMLInputElement>) => {
    const pasted = e.clipboardData.getData('text');
    if (pasted.includes('\n')) {
      e.preventDefault();
      const lines = pasted.split('\n').map((l) => l.trim()).filter(Boolean);
      const updated = [...urls];
      updated.splice(index, 1, ...lines);
      onChange(updated.slice(0, max));
    }
  };

  return (
    <div className="space-y-2">
      {urls.map((url, i) => (
        <div key={i} className="flex items-center gap-2">
          <Input
            type="url"
            placeholder="https://..."
            value={url}
            onChange={(e) => updateUrl(i, e.target.value)}
            onPaste={(e) => handlePaste(i, e)}
            className="flex-1"
          />
          {urls.length > 1 && (
            <button
              type="button"
              onClick={() => removeUrl(i)}
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-secondary-text hover:bg-hover hover:text-danger transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      ))}
      {urls.length < max && (
        <Button variant="ghost" size="sm" onClick={addUrl}>
          <Plus className="h-4 w-4" />
          <span>添加 URL</span>
        </Button>
      )}
    </div>
  );
};
