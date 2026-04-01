import type { Message } from '../stores/agentChatStore';

/**
 * Format chat messages as Markdown for export.
 */
export function formatSessionAsMarkdown(messages: Message[]): string {
  const now = new Date();
  const timeStr = now.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });

  const lines: string[] = [
    '# 问股会话',
    '',
    `生成时间: ${timeStr}`,
    '',
  ];

  for (const msg of messages) {
    const heading = msg.role === 'user' ? '## 用户' : '## AI';
    if (msg.role === 'assistant' && msg.skillName) {
      lines.push(`${heading} (${msg.skillName})`);
    } else {
      lines.push(heading);
    }
    lines.push('');
    lines.push(msg.content);
    lines.push('');
  }

  return lines.join('\n');
}

/**
 * Escape HTML special characters to prevent XSS.
 */
function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * Simple Markdown-to-HTML renderer for export purposes.
 * Handles: headings, bold, italic, tables, code blocks, inline code, lists, blockquotes.
 */
function renderMarkdownToHtml(md: string): string {
  let html = escapeHtml(md);

  // Code blocks (```lang\n...\n```)
  html = html.replace(
    /```(\w*)\n([\s\S]*?)```/g,
    (_m: string, _lang: string, code: string) => {
      return '<pre style="background:#1e2433;border-radius:8px;padding:12px 16px;overflow-x:auto;font-size:13px;margin:8px 0;"><code>' + code.trim() + '</code></pre>';
    }
  );

  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code style="background:#1e2433;border-radius:4px;padding:1px 6px;font-size:0.88em;font-family:monospace;color:#79b8ff;">$1</code>');

  // Tables
  html = html.replace(
    /^\|(.+)\|\s*\n\|[-| :]+\|\n((?:\|.+\|\n?)*)/gm,
    (_m: string, headerRow: string, bodyRows: string) => {
      const headerCells = headerRow.split('|').map((c: string) => c.trim()).filter(Boolean);
      const thead =
        '<thead><tr>' +
        headerCells
          .map(
            (c: string) =>
              '<th style="text-align:left;padding:8px 12px;color:#8b8fa3;font-size:0.78rem;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;border-bottom:1px solid #2a2d3a;">' +
              c +
              '</th>'
          )
          .join('') +
        '</tr></thead>';

      const bodyLines = bodyRows.trim().split('\n');
      const tbody =
        '<tbody>' +
        bodyLines
          .map((row: string) => {
            const cells = row.replace(/^\||\|$/g, '').split('|').map((c: string) => c.trim());
            return (
              '<tr>' +
              cells
                .map((c: string) => '<td style="padding:8px 12px;border-bottom:1px solid rgba(42,45,58,0.5);font-size:0.88rem;">' + c + '</td>')
                .join('') +
              '</tr>'
            );
          })
          .join('') +
        '</tbody>';

      return '<table style="width:100%;border-collapse:collapse;margin:12px 0;font-size:0.88rem;">' + thead + tbody + '</table>';
    }
  );

  // Blockquotes
  html = html.replace(
    /^> (.+)$/gm,
    '<blockquote style="border-left:3px solid #5b8dee;margin:8px 0;padding:6px 12px;color:#8b8fa3;background:rgba(91,141,238,0.08);border-radius:0 6px 6px 0;">$1</blockquote>'
  );

  // Headings
  html = html.replace(/^### (.+)$/gm, '<h3 style="font-size:1rem;font-weight:700;color:#e2e4ea;margin:16px 0 6px;">$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2 style="font-size:1.15rem;font-weight:700;color:#e2e4ea;margin:20px 0 8px;border-bottom:1px solid #2a2d3a;padding-bottom:6px;">$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h1 style="font-size:1.4rem;font-weight:700;color:#fff;margin:0 0 4px;">$1</h1>');

  // Bold + Italic
  html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong style="color:#fff;">$1</strong>');
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
  html = html.replace(/__(.+?)__/g, '<strong style="color:#fff;">$1</strong>');
  html = html.replace(/_(.+?)_/g, '<em>$1</em>');

  // Lists: collect consecutive li items into ul
  html = html.replace(
    /^[*-] (.+)$/gm,
    '<li style="margin:4px 0 4px 20px;color:#c8ccd4;">$1</li>'
  );
  html = html.replace(
    /(<li[^>]*>[\s\S]*?<\/li>\n?)+/g,
    (match: string) => '<ul style="margin:8px 0;padding-left:0;list-style:none;">' + match + '</ul>'
  );

  // Ordered lists
  html = html.replace(
    /^\d+\. (.+)$/gm,
    '<li style="margin:4px 0 4px 20px;color:#c8ccd4;">$1</li>'
  );

  // Horizontal rule
  html = html.replace(
    /^---$/gm,
    '<hr style="border:none;border-top:1px solid #2a2d3a;margin:16px 0;"/>'
  );

  // Paragraphs and line breaks
  html = html.replace(
    /\n\n/g,
    '</p><p style="margin:6px 0;color:#c8ccd4;line-height:1.7;">'
  );
  html = html.replace(/\n/g, '<br/>');

  // Wrap in paragraph
  html = '<p style="margin:6px 0;color:#c8ccd4;line-height:1.7;">' + html + '</p>';

  return html;
}

/**
 * Format chat messages as a styled HTML document for export.
 */
export function formatSessionAsHtml(messages: Message[]): string {
  const now = new Date();
  const timeStr = now.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });

  const messagesHtml = messages
    .map((msg) => {
      const skillTag =
        msg.role === 'assistant' && msg.skillName
          ? '<span style="display:inline-flex;align-items:center;gap:4px;background:rgba(91,141,238,0.15);color:#5b8dee;border-radius:20px;padding:2px 10px;font-size:0.75rem;font-weight:600;margin-bottom:8px;">&#x26A1; ' +
            escapeHtml(msg.skillName) +
            '</span>'
          : '';

      const avatarBg = msg.role === 'user'
        ? 'background:linear-gradient(135deg,#4f46e5,#818cf8);'
        : 'background:linear-gradient(135deg,#0ea5e9,#38bdf8);';

      const bubbleBg = msg.role === 'user'
        ? 'background:rgba(99,102,241,0.18);border-color:rgba(99,102,241,0.35);'
        : 'background:rgba(14,165,233,0.08);border-color:rgba(14,165,233,0.2);';

      const contentHtml =
        msg.role === 'assistant'
          ? renderMarkdownToHtml(msg.content)
          : escapeHtml(msg.content).replace(/\n/g, '<br/>');

      return (
        '<div style="display:flex;flex-direction:' +
        (msg.role === 'user' ? 'row-reverse' : 'row') +
        ';gap:12px;margin-bottom:20px;align-items:flex-start;">' +
        '<div style="width:36px;height:36px;border-radius:50%;' +
        avatarBg +
        'display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:#fff;flex-shrink:0;box-shadow:0 2px 8px rgba(0,0,0,0.3);">' +
        (msg.role === 'user' ? 'U' : 'AI') +
        '</div>' +
        '<div style="max-width:80%;min-width:0;' +
        bubbleBg +
        'border-radius:16px;padding:12px 16px;border-width:1px;border-style:solid;">' +
        skillTag +
        '<div style="font-size:0.9rem;line-height:1.7;color:#c8ccd4;word-break:break-word;">' +
        contentHtml +
        '</div></div></div>'
      );
    })
    .join('');

  return (
    '<!DOCTYPE html>\n' +
    '<html lang="zh-CN">\n' +
    '<head>\n' +
    '<meta charset="UTF-8">\n' +
    '<meta name="viewport" content="width=device-width,initial-scale=1.0">\n' +
    '<title>问股会话 · ' +
    timeStr +
    '</title>\n' +
    '<style>\n' +
    '  * { box-sizing: border-box; margin: 0; padding: 0; }\n' +
    '  body { font-family: "Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; background: #0f1117; color: #e2e4ea; line-height: 1.7; padding: 2rem 1rem; }\n' +
    '  .container { max-width: 800px; margin: 0 auto; }\n' +
    '  .header { text-align: center; margin-bottom: 2rem; padding-bottom: 1.5rem; border-bottom: 1px solid #2a2d3a; }\n' +
    '  .header h1 { font-size: 1.5rem; font-weight: 700; color: #fff; margin-bottom: 4px; letter-spacing: -0.02em; }\n' +
    '  .header .meta { font-size: 0.8rem; color: #8b8fa3; }\n' +
    '  @media (max-width: 600px) { body { padding: 1rem 0.5rem; } }\n' +
    '</style>\n' +
    '</head>\n' +
    '<body>\n' +
    '<div class="container">\n' +
    '<div class="header">\n' +
    '<h1>&#x1F4CA; 问股会话</h1>\n' +
    '<p class="meta">生成时间: ' +
    timeStr +
    '</p>\n' +
    '</div>\n' +
    messagesHtml +
    '\n' +
    '</div>\n' +
    '</body>\n' +
    '</html>'
  );
}

/**
 * Trigger browser download of session as .md file.
 */
export function downloadSession(messages: Message[]): void {
  const content = formatSessionAsMarkdown(messages);
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
  const now = new Date();
  const dateStr = now.toISOString().slice(0, 10).replace(/-/g, '');
  const pad = (n: number) => n.toString().padStart(2, '0');
  const timeStr = pad(now.getHours()) + pad(now.getMinutes());
  const filename = '问股会话_' + dateStr + '_' + timeStr + '.md';

  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/**
 * Trigger browser download of session as .html file.
 */
export function downloadSessionAsHtml(messages: Message[]): void {
  const content = formatSessionAsHtml(messages);
  const blob = new Blob([content], { type: 'text/html;charset=utf-8' });
  const now = new Date();
  const dateStr = now.toISOString().slice(0, 10).replace(/-/g, '');
  const pad = (n: number) => n.toString().padStart(2, '0');
  const timeStr = pad(now.getHours()) + pad(now.getMinutes());
  const filename = '问股会话_' + dateStr + '_' + timeStr + '.html';

  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ─── Single message export ────────────────────────────────────────────────────

/**
 * Format a single message as Markdown.
 */
function formatMessageAsMarkdown(msg: Message): string {
  const heading = msg.role === 'user' ? '# 用户消息' : '# AI 回复' + (msg.skillName ? ` · ${msg.skillName}` : '');
  return [heading, '', msg.content].join('\n');
}

/**
 * Format a single message as a styled HTML document.
 */
function formatMessageAsHtml(msg: Message): string {
  const skillTag =
    msg.role === 'assistant' && msg.skillName
      ? '<span style="display:inline-flex;align-items:center;gap:4px;background:rgba(91,141,238,0.15);color:#5b8dee;border-radius:20px;padding:2px 10px;font-size:0.75rem;font-weight:600;margin-bottom:8px;">&#x26A1; ' +
        escapeHtml(msg.skillName) +
        '</span>'
      : '';

  const avatarBg = msg.role === 'user'
    ? 'background:linear-gradient(135deg,#4f46e5,#818cf8);'
    : 'background:linear-gradient(135deg,#0ea5e9,#38bdf8);';

  const bubbleBg = msg.role === 'user'
    ? 'background:rgba(99,102,241,0.18);border-color:rgba(99,102,241,0.35);'
    : 'background:rgba(14,165,233,0.08);border-color:rgba(14,165,233,0.2);';

  const contentHtml =
    msg.role === 'assistant'
      ? renderMarkdownToHtml(msg.content)
      : escapeHtml(msg.content).replace(/\n/g, '<br/>');

  const now = new Date();
  const timeStr = now.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });

  return (
    '<!DOCTYPE html>\n' +
    '<html lang="zh-CN">\n' +
    '<head>\n' +
    '<meta charset="UTF-8">\n' +
    '<meta name="viewport" content="width=device-width,initial-scale=1.0">\n' +
    '<title>' +
    (msg.role === 'user' ? '用户消息' : 'AI 回复') +
    (msg.skillName ? ' · ' + msg.skillName : '') +
    ' · ' +
    timeStr +
    '</title>\n' +
    '<style>\n' +
    '  * { box-sizing: border-box; margin: 0; padding: 0; }\n' +
    '  body { font-family: "Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; background: #0f1117; color: #e2e4ea; line-height: 1.7; padding: 2rem 1rem; }\n' +
    '  .container { max-width: 800px; margin: 0 auto; }\n' +
    '  .header { text-align: center; margin-bottom: 2rem; padding-bottom: 1.5rem; border-bottom: 1px solid #2a2d3a; }\n' +
    '  .header h1 { font-size: 1.5rem; font-weight: 700; color: #fff; margin-bottom: 4px; letter-spacing: -0.02em; }\n' +
    '  .header .meta { font-size: 0.8rem; color: #8b8fa3; }\n' +
    '  @media (max-width: 600px) { body { padding: 1rem 0.5rem; } }\n' +
    '</style>\n' +
    '</head>\n' +
    '<body>\n' +
    '<div class="container">\n' +
    '<div class="header">\n' +
    '<h1>' +
    (msg.role === 'user' ? '&#x1F464; 用户消息' : '&#x1F916; AI 回复') +
    (msg.skillName ? ' · ' + escapeHtml(msg.skillName) : '') +
    '</h1>\n' +
    '<p class="meta">生成时间: ' +
    timeStr +
    '</p>\n' +
    '</div>\n' +
    '<div style="display:flex;flex-direction:' +
    (msg.role === 'user' ? 'row-reverse' : 'row') +
    ';gap:12px;margin-bottom:20px;align-items:flex-start;">' +
    '<div style="width:36px;height:36px;border-radius:50%;' +
    avatarBg +
    'display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:#fff;flex-shrink:0;box-shadow:0 2px 8px rgba(0,0,0,0.3);">' +
    (msg.role === 'user' ? 'U' : 'AI') +
    '</div>' +
    '<div style="max-width:80%;min-width:0;' +
    bubbleBg +
    'border-radius:16px;padding:12px 16px;border-width:1px;border-style:solid;">' +
    skillTag +
    '<div style="font-size:0.9rem;line-height:1.7;color:#c8ccd4;word-break:break-word;">' +
    contentHtml +
    '</div></div></div>\n' +
    '</div>\n' +
    '</body>\n' +
    '</html>'
  );
}

/**
 * Download a single message as .md file.
 */
export function downloadMessageAsMarkdown(msg: Message): void {
  const content = formatMessageAsMarkdown(msg);
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
  const filename =
    (msg.role === 'user' ? 'user' : 'assistant') + '-message-' + msg.id + '.md';
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/**
 * Download a single message as .html file.
 */
export function downloadMessageAsHtml(msg: Message): void {
  const content = formatMessageAsHtml(msg);
  const blob = new Blob([content], { type: 'text/html;charset=utf-8' });
  const filename =
    (msg.role === 'user' ? 'user' : 'assistant') + '-message-' + msg.id + '.html';
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
