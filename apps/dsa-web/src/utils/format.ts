export const formatDateTime = (value?: string | null): string => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
};

export const formatDate = (value?: string): string => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(date);
};

export const toDateInputValue = (date: Date): string => {
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, '0');
  const day = `${date.getDate()}`.padStart(2, '0');
  return `${year}-${month}-${day}`;
};

/**
 * Returns the date N days ago as YYYY-MM-DD in Asia/Seoul timezone.
 * Consistent with getTodayInSeoul() so both ends of the date range
 * are expressed in the same timezone as the KR/US-focused product surface.
 */
export const getRecentStartDate = (days: number): string => {
  const date = new Date();
  date.setDate(date.getDate() - days);
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Seoul' }).format(date);
};

/**
 * Returns today's date as YYYY-MM-DD in Asia/Seoul timezone.
 * Use this instead of browser-local date to stay consistent with the backend,
 * which stores and filters timestamps in server local time for this deployment.
 */
export const getTodayInShanghai = (): string =>
  new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Seoul' }).format(new Date());

export const formatReportType = (value?: string): string => {
  if (!value) return '—';
  if (value === 'simple') return '일반';
  if (value === 'detailed') return '표준';
  return value;
};
