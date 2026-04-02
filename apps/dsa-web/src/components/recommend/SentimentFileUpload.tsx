import React, { useCallback } from 'react';
import { FileUp, X } from 'lucide-react';

interface SentimentFileUploadProps {
  files: File[];
  onChange: (files: File[]) => void;
  max?: number;
  maxSizeMb?: number;
}

const ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.txt', '.md'];

export const SentimentFileUpload: React.FC<SentimentFileUploadProps> = ({
  files,
  onChange,
  max = 5,
  maxSizeMb = 2,
}) => {
  const maxSize = maxSizeMb * 1024 * 1024;

  const handleFiles = useCallback(
    (incoming: FileList | null) => {
      if (!incoming) return;
      const valid: File[] = [];
      for (const f of Array.from(incoming)) {
        const ext = '.' + f.name.split('.').pop()?.toLowerCase();
        if (!ALLOWED_EXTENSIONS.includes(ext)) continue;
        if (f.size > maxSize) continue;
        valid.push(f);
      }
      const merged = [...files, ...valid].slice(0, max);
      onChange(merged);
    },
    [files, max, maxSize, onChange],
  );

  const removeFile = (index: number) => {
    onChange(files.filter((_, i) => i !== index));
  };

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      handleFiles(e.dataTransfer.files);
    },
    [handleFiles],
  );

  return (
    <div className="space-y-2">
      <div
        onDrop={handleDrop}
        onDragOver={(e) => e.preventDefault()}
        className="flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-border/50 bg-base/50 py-6 text-center text-secondary-text transition-colors hover:border-cyan/30 hover:bg-base/80"
      >
        <FileUp className="h-6 w-6" />
        <p className="text-sm">
          拖放文件到此处，或{' '}
          <label className="cursor-pointer text-cyan hover:underline">
            点击选择
            <input
              type="file"
              multiple
              accept={ALLOWED_EXTENSIONS.join(',')}
              className="hidden"
              onChange={(e) => handleFiles(e.target.files)}
            />
          </label>
        </p>
        <p className="text-xs text-secondary-text/70">
          支持 PDF / DOCX / TXT / MD，单个不超过 {maxSizeMb}MB，最多 {max} 个
        </p>
      </div>

      {files.length > 0 && (
        <div className="space-y-1">
          {files.map((f, i) => (
            <div
              key={`${f.name}-${i}`}
              className="flex items-center justify-between rounded-lg bg-elevated/50 px-3 py-2 text-sm"
            >
              <span className="truncate text-foreground">{f.name}</span>
              <div className="flex items-center gap-2">
                <span className="text-xs text-secondary-text">
                  {(f.size / 1024).toFixed(0)} KB
                </span>
                <button
                  type="button"
                  onClick={() => removeFile(i)}
                  className="text-secondary-text hover:text-danger transition-colors"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
