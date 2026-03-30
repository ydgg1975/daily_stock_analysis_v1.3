import React, { useState } from 'react';

interface JsonViewerProps {
  data: Record<string, unknown> | unknown[] | null | undefined;
  maxHeight?: string;
  className?: string;
}

/**
 * JSON 结构化展示组件
 * 支持语法高亮和折叠
 */
export const JsonViewer: React.FC<JsonViewerProps> = ({
  data,
  maxHeight = '400px',
  className = '',
}) => {
  const [copied, setCopied] = useState(false);

  if (!data) {
    return (
      <div className="py-4 text-center italic text-muted-text">暂无数据</div>
    );
  }

  const jsonString = JSON.stringify(data, null, 2);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(jsonString);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // 简单的语法高亮
  const highlightJson = (json: string): React.ReactNode => {
    return json.split('\n').map((line, index) => {
      // 高亮 key
      let highlighted = line.replace(
        /"([^"]+)":/g,
        '<span class="theme-json-key">"$1"</span>:'
      );
      // 高亮字符串值
      highlighted = highlighted.replace(
        /: "([^"]*)"/g,
        ': <span class="theme-json-string">"$1"</span>'
      );
      // 高亮数字
      highlighted = highlighted.replace(
        /: (-?\d+\.?\d*)/g,
        ': <span class="theme-json-number">$1</span>'
      );
      // 高亮布尔值和 null
      highlighted = highlighted.replace(
        /: (true|false|null)/g,
        ': <span class="theme-json-literal">$1</span>'
      );

      return (
        <div
          key={index}
          className="leading-relaxed"
          dangerouslySetInnerHTML={{ __html: highlighted }}
        />
      );
    });
  };

  return (
    <div className={`relative ${className}`}>
      {/* 复制按钮 */}
      <button
        onClick={handleCopy}
        className="absolute right-2 top-2 z-10 rounded border border-[var(--border-muted)] bg-[var(--pill-bg)] px-2 py-1 text-xs text-secondary-text transition-colors hover:border-[var(--border-strong)] hover:bg-[var(--pill-active-bg)] hover:text-foreground"
      >
        {copied ? '已复制!' : '复制'}
      </button>

      {/* JSON 内容 */}
      <div
        className="theme-panel-subtle custom-scrollbar overflow-auto rounded-lg border p-4 font-mono text-sm text-secondary-text"
        style={{ maxHeight }}
      >
        <pre className="whitespace-pre-wrap break-words">
          {highlightJson(jsonString)}
        </pre>
      </div>
    </div>
  );
};
