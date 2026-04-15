import axios from 'axios';

export type ApiErrorCategory =
  | 'auth_required'
  | 'access_denied'
  | 'admin_unlock_required'
  | 'agent_disabled'
  | 'missing_params'
  | 'validation_error'
  | 'analysis_conflict'
  | 'llm_not_configured'
  | 'model_tool_incompatible'
  | 'invalid_tool_call'
  | 'portfolio_oversell'
  | 'portfolio_busy'
  | 'upstream_forbidden'
  | 'upstream_unavailable'
  | 'upstream_llm_400'
  | 'upstream_timeout'
  | 'upstream_network'
  | 'local_connection_failed'
  | 'http_error'
  | 'unknown';

export interface ParsedApiError {
  title: string;
  message: string;
  rawMessage: string;
  status?: number;
  category: ApiErrorCategory;
}

type ResponseLike = {
  status?: number;
  data?: unknown;
  statusText?: string;
};

type ErrorCarrier = {
  response?: ResponseLike;
  code?: string;
  message?: string;
  parsedError?: ParsedApiError;
  cause?: unknown;
};

type CreateParsedApiErrorOptions = {
  title: string;
  message: string;
  rawMessage?: string;
  status?: number;
  category?: ApiErrorCategory;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function pickString(...values: unknown[]): string | null {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) {
      return value.trim();
    }
  }
  return null;
}

function stringifyValue(value: unknown): string | null {
  if (value === null || value === undefined) {
    return null;
  }

  if (typeof value === 'string') {
    return value.trim() || null;
  }

  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }

  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function getResponse(error: unknown): ResponseLike | undefined {
  if (!isRecord(error)) {
    return undefined;
  }

  const response = (error as ErrorCarrier).response;
  return response && typeof response === 'object' ? response : undefined;
}

function getErrorCode(error: unknown): string | undefined {
  return isRecord(error) && typeof (error as ErrorCarrier).code === 'string'
    ? (error as ErrorCarrier).code
    : undefined;
}

function getErrorMessage(error: unknown): string | null {
  if (typeof error === 'string') {
    return error.trim() || null;
  }

  if (error instanceof Error && error.message.trim()) {
    return error.message.trim();
  }

  if (isRecord(error) && typeof (error as ErrorCarrier).message === 'string') {
    const message = (error as ErrorCarrier).message?.trim();
    return message || null;
  }

  return null;
}

function getCauseMessage(error: unknown): string | null {
  if (!isRecord(error)) {
    return null;
  }

  return getErrorMessage((error as ErrorCarrier).cause);
}

function buildMatchText(parts: Array<string | undefined | null>): string {
  return parts
    .filter((part): part is string => typeof part === 'string' && part.trim().length > 0)
    .join(' | ')
    .toLowerCase();
}

function includesAny(haystack: string, needles: string[]): boolean {
  return needles.some((needle) => haystack.includes(needle.toLowerCase()));
}

function extractValidationDetail(detail: unknown): string | null {
  if (!Array.isArray(detail)) {
    return null;
  }

  const parts = detail
    .map((item) => {
      if (!isRecord(item)) {
        return stringifyValue(item);
      }

      const location = Array.isArray(item.loc)
        ? item.loc.map((segment) => String(segment)).join('.')
        : null;
      const message = pickString(item.msg, item.message, item.error);
      if (!location && !message) {
        return stringifyValue(item);
      }
      return [location, message].filter(Boolean).join(': ');
    })
    .filter((entry): entry is string => Boolean(entry));

  return parts.length > 0 ? parts.join('; ') : null;
}

function extractErrorCode(data: unknown): string | null {
  if (!isRecord(data)) {
    return null;
  }

  const detail = data.detail;
  if (isRecord(detail)) {
    return pickString(detail.error, detail.code, data.error, data.code);
  }

  return pickString(data.error, data.code);
}

export function extractErrorPayloadText(data: unknown): string | null {
  if (typeof data === 'string') {
    return data.trim() || null;
  }

  if (Array.isArray(data)) {
    return extractValidationDetail(data) ?? stringifyValue(data);
  }

  if (!isRecord(data)) {
    return stringifyValue(data);
  }

  const detail = data.detail;
  if (isRecord(detail)) {
    return (
      pickString(detail.message, detail.error)
      ?? extractValidationDetail(detail.detail)
      ?? stringifyValue(detail)
    );
  }

  return (
    pickString(
      detail,
      data.message,
      data.error,
      data.title,
      data.reason,
      data.description,
      data.msg,
    )
    ?? extractValidationDetail(detail)
    ?? stringifyValue(data)
  );
}

export function createParsedApiError(options: CreateParsedApiErrorOptions): ParsedApiError {
  return {
    title: options.title,
    message: options.message,
    rawMessage: options.rawMessage?.trim() || options.message,
    status: options.status,
    category: options.category ?? 'unknown',
  };
}

export function isParsedApiError(value: unknown): value is ParsedApiError {
  return isRecord(value)
    && typeof value.title === 'string'
    && typeof value.message === 'string'
    && typeof value.rawMessage === 'string'
    && typeof value.category === 'string';
}

export function isApiRequestError(
  value: unknown,
): value is Error & ErrorCarrier & { parsedError: ParsedApiError } {
  return value instanceof Error
    && isRecord(value)
    && isParsedApiError((value as ErrorCarrier).parsedError);
}

export function formatParsedApiError(parsed: ParsedApiError): string {
  if (!parsed.title.trim()) {
    return parsed.message;
  }
  if (parsed.title === parsed.message) {
    return parsed.title;
  }
  return `${parsed.title}：${parsed.message}`;
}

export function getParsedApiError(error: unknown): ParsedApiError {
  if (isParsedApiError(error)) {
    return error;
  }
  if (isRecord(error) && isParsedApiError((error as ErrorCarrier).parsedError)) {
    return (error as ErrorCarrier).parsedError as ParsedApiError;
  }
  return parseApiError(error);
}

export function createApiError(
  parsed: ParsedApiError,
  extra: { response?: ResponseLike; code?: string; cause?: unknown } = {},
): Error & ErrorCarrier & { status?: number; category: ApiErrorCategory; rawMessage: string } {
  const apiError = new Error(formatParsedApiError(parsed)) as Error & ErrorCarrier & {
    status?: number;
    category: ApiErrorCategory;
    rawMessage: string;
  };
  apiError.name = 'ApiRequestError';
  apiError.parsedError = parsed;
  apiError.response = extra.response;
  apiError.code = extra.code;
  apiError.status = parsed.status;
  apiError.category = parsed.category;
  apiError.rawMessage = parsed.rawMessage;
  if (extra.cause !== undefined) {
    apiError.cause = extra.cause;
  }
  return apiError;
}

export function attachParsedApiError(error: unknown): ParsedApiError {
  const parsed = parseApiError(error);
  if (isRecord(error)) {
    const carrier = error as ErrorCarrier;
    carrier.parsedError = parsed;
  }
  if (error instanceof Error) {
    error.name = 'ApiRequestError';
    error.message = formatParsedApiError(parsed);
  }
  return parsed;
}

export function isLocalConnectionFailure(error: unknown): boolean {
  return parseApiError(error).category === 'local_connection_failed';
}

export function parseApiError(error: unknown): ParsedApiError {
  const response = getResponse(error);
  const status = response?.status;
  const payloadText = extractErrorPayloadText(response?.data);
  const errorCode = extractErrorCode(response?.data);
  const errorMessage = getErrorMessage(error);
  const causeMessage = getCauseMessage(error);
  const code = getErrorCode(error);
  const rawMessage = pickString(payloadText, response?.statusText, errorMessage, causeMessage, code)
    ?? '请求未成功完成，请稍后重试。';
  const matchText = buildMatchText([rawMessage, errorMessage, causeMessage, code, errorCode, response?.statusText]);

  if (includesAny(matchText, ['agent mode is not enabled', 'agent_mode'])) {
    return createParsedApiError({
      title: 'Agent 模式未开启',
      message: '当前功能依赖 Agent 模式，请先开启后再重试。',
      rawMessage,
      status,
      category: 'agent_disabled',
    });
  }

  const hasStockCodeField = includesAny(matchText, ['stock_code', 'stock_codes']);
  const hasMissingParamText = includesAny(matchText, ['必须提供 stock_code 或 stock_codes', 'missing', 'required']);
  if (hasStockCodeField && hasMissingParamText) {
    return createParsedApiError({
      title: '请求缺少必要参数',
      message: '请先补充股票代码或必要输入后再试。',
      rawMessage,
      status,
      category: 'missing_params',
    });
  }

  if (
    errorCode === 'duplicate_task'
    || includesAny(matchText, ['正在分析中', 'duplicate task', 'duplicate_task'])
    || (status === 409 && !errorCode)
  ) {
    return createParsedApiError({
      title: '分析任务已在进行中',
      message: '同一标的已有分析任务正在运行，请等待当前任务完成后再试。',
      rawMessage,
      status,
      category: 'analysis_conflict',
    });
  }

  if (errorCode === 'portfolio_oversell' || includesAny(matchText, ['oversell detected'])) {
    return createParsedApiError({
      title: '卖出数量超过可用持仓',
      message: '卖出数量超过当前可用持仓，请删除或修正对应卖出流水后重试。',
      rawMessage,
      status,
      category: 'portfolio_oversell',
    });
  }

  if (
    errorCode === 'ibkr_session_required'
    || errorCode === 'ibkr_session_invalid'
    || errorCode === 'ibkr_session_expired'
  ) {
    return createParsedApiError({
      title: 'IBKR 会话不可用',
      message: '请先在本地 IBKR Client Portal / Gateway 中确认只读会话仍有效，再重新粘贴 session token 后重试。',
      rawMessage,
      status,
      category: 'validation_error',
    });
  }

  if (errorCode === 'ibkr_account_mapping_conflict') {
    return createParsedApiError({
      title: 'IBKR 账户映射冲突',
      message: '该 broker account ref 已绑定到另一持仓账户。请先确认账户映射，再重新同步。',
      rawMessage,
      status,
      category: 'validation_error',
    });
  }

  if (
    errorCode === 'ibkr_account_ambiguous'
    || errorCode === 'ibkr_account_not_found'
    || errorCode === 'ibkr_account_identifier_invalid'
    || errorCode === 'ibkr_empty_accounts'
    || errorCode === 'ibkr_connection_not_found'
    || errorCode === 'ibkr_connection_type_invalid'
  ) {
    return createParsedApiError({
      title: '无法确定要同步的 IBKR 账户',
      message: '请确认当前 session 暴露了正确账户，并填写或复用正确的 broker account ref 后再试。',
      rawMessage,
      status,
      category: 'validation_error',
    });
  }

  if (errorCode === 'ibkr_payload_unsupported') {
    return createParsedApiError({
      title: '当前 IBKR 返回结构暂不受支持',
      message: '本次只读同步没有拿到当前版本可安全解析的账户数据。请改用 Flex 导入，或等待后端适配后再试。',
      rawMessage,
      status,
      category: 'validation_error',
    });
  }

  if (errorCode === 'ibkr_upstream_error' || errorCode === 'ibkr_sync_internal_error') {
    return createParsedApiError({
      title: 'IBKR 只读同步暂时失败',
      message: '本地工作台仍可用，但这次 IBKR 只读同步没有完成。请稍后重试，或先改用 Flex 导入。',
      rawMessage,
      status,
      category: 'upstream_unavailable',
    });
  }

  if (
    errorCode === 'unauthorized'
    || includesAny(matchText, ['login required', 'not authenticated'])
  ) {
    return createParsedApiError({
      title: '需要登录',
      message: '当前操作需要先登录后继续。登录成功后，请重新进入刚才的页面。',
      rawMessage,
      status,
      category: 'auth_required',
    });
  }

  if (
    errorCode === 'admin_unlock_required'
    || includesAny(matchText, ['admin settings are locked', 'verify admin password'])
  ) {
    return createParsedApiError({
      title: '管理员验证已过期',
      message: '请先重新验证管理员密码，再继续访问系统设置或管理员日志。',
      rawMessage,
      status,
      category: 'admin_unlock_required',
    });
  }

  if (
    errorCode === 'admin_required'
    || includesAny(matchText, ['admin access required'])
  ) {
    return createParsedApiError({
      title: '需要管理员账户',
      message: '当前页面或操作仅对管理员开放，请切换到管理员账户后再试。',
      rawMessage,
      status,
      category: 'access_denied',
    });
  }

  if (
    errorCode === 'owner_mismatch'
    || includesAny(matchText, ['owner_id does not match the current user'])
  ) {
    return createParsedApiError({
      title: '无法访问其他用户的数据',
      message: '当前账户只能访问自己的数据，请返回允许的页面继续使用。',
      rawMessage,
      status,
      category: 'access_denied',
    });
  }

  if (
    status === 403
    || includesAny(matchText, ['403 forbidden', 'status code 403', 'forbidden for url'])
  ) {
    if (includesAny(matchText, ['fmp', 'financialmodelingprep'])) {
      return createParsedApiError({
        title: '上游数据源拒绝访问',
        message: 'FMP 返回了 403，可能是 API Key、额度或权限限制。请稍后重试或检查相关配置。',
        rawMessage,
        status,
        category: 'upstream_forbidden',
      });
    }

    if (includesAny(matchText, ['gemini', 'generativelanguage', 'google'])) {
      return createParsedApiError({
        title: '上游模型拒绝访问',
        message: 'Gemini 返回了 403，可能是模型权限、Key 配额或渠道配置问题。',
        rawMessage,
        status,
        category: 'upstream_forbidden',
      });
    }

    return createParsedApiError({
      title: '当前账户无权执行该操作',
      message: '该请求被拒绝。请返回允许的页面，或切换到具备权限的账户后再试。',
      rawMessage,
      status,
      category: 'access_denied',
    });
  }

  if (errorCode === 'portfolio_busy' || includesAny(matchText, ['portfolio ledger is busy'])) {
    return createParsedApiError({
      title: '持仓账本正忙',
      message: '持仓账本正在处理另一笔变更，请稍后重试。',
      rawMessage,
      status,
      category: 'portfolio_busy',
    });
  }

  const noConfiguredLlm = (
    includesAny(matchText, ['all llm models failed']) && includesAny(matchText, ['last error: none'])
  ) || includesAny(matchText, [
    'no llm configured',
    'litellm_model not configured',
    'ai analysis will be unavailable',
  ]);
  if (noConfiguredLlm) {
    return createParsedApiError({
      title: '系统没有配置可用的 LLM 模型',
      message: '请先在系统设置中配置主模型、可用渠道或相关 API Key 后再重试。',
      rawMessage,
      status,
      category: 'llm_not_configured',
    });
  }

  if (includesAny(matchText, [
    'tool call',
    'function call',
    'does not support tools',
    'tools is not supported',
    'reasoning',
  ])) {
    return createParsedApiError({
      title: '当前模型不兼容工具调用',
      message: '当前模型不适合 Agent / 工具调用场景，请更换支持工具调用的模型后重试。',
      rawMessage,
      status,
      category: 'model_tool_incompatible',
    });
  }

  if (includesAny(matchText, [
    'thought_signature',
    'missing function',
    'missing tool',
    'invalid tool call',
    'invalid function call',
  ])) {
    return createParsedApiError({
      title: '上游模型返回的数据结构不完整',
      message: '上游模型返回的工具调用结构不符合要求，请更换模型或关闭相关推理模式后重试。',
      rawMessage,
      status,
      category: 'invalid_tool_call',
    });
  }

  if (includesAny(matchText, ['timeout', 'timed out', 'read timeout', 'connect timeout']) || code === 'ECONNABORTED') {
    return createParsedApiError({
      title: '连接上游服务超时',
      message: '服务端访问外部依赖时超时，请稍后重试，或检查当前网络与代理设置。',
      rawMessage,
      status,
      category: 'upstream_timeout',
    });
  }

  if (
    status === 502
    || status === 503
    || includesAny(matchText, [
      'dns',
      'enotfound',
      'name or service not known',
      'temporary failure in name resolution',
      'proxy',
      'tunnel',
      '502',
      '503',
    ])
  ) {
    if (includesAny(matchText, ['gemini', 'generativelanguage', 'model overloaded', 'service unavailable'])) {
      return createParsedApiError({
        title: '上游模型暂时不可用',
        message: 'Gemini 当前繁忙或临时不可用，系统会在下一次分析时继续重试，请稍后再试。',
        rawMessage,
        status,
        category: 'upstream_unavailable',
      });
    }

    return createParsedApiError({
      title: '服务端无法访问外部依赖',
      message: '页面已连接到本地服务，但本地服务访问外部模型或数据接口失败，请检查代理、DNS 或出网配置。',
      rawMessage,
      status,
      category: 'upstream_network',
    });
  }

  const hasLlmProviderHint = includesAny(matchText, [
    'chat/completions',
    'generativelanguage',
    'openai',
    'gemini',
  ]);
  if (status === 400 && hasLlmProviderHint) {
    return createParsedApiError({
      title: '上游模型接口拒绝了当前请求',
      message: '本地服务正常，但上游模型接口拒绝了请求，请检查模型名称、参数格式或工具调用兼容性。',
      rawMessage,
      status,
      category: 'upstream_llm_400',
    });
  }

  const localConnectionFailed = !response && (
    includesAny(matchText, ['fetch failed', 'failed to fetch', 'network error', 'connection refused', 'econnrefused'])
    || code === 'ERR_NETWORK'
    || code === 'ECONNREFUSED'
  );
  if (localConnectionFailed) {
    return createParsedApiError({
      title: '无法连接到本地服务',
      message: '浏览器当前无法连接到本地 Web 服务，请检查服务是否启动、监听地址是否正确、端口是否开放。',
      rawMessage,
      status,
      category: 'local_connection_failed',
    });
  }

  if (payloadText || status) {
    return createParsedApiError({
      title: '请求失败',
      message: payloadText ?? `请求未成功完成（HTTP ${status}）。`,
      rawMessage,
      status,
      category: 'http_error',
    });
  }

  return createParsedApiError({
    title: '请求失败',
    message: rawMessage,
    rawMessage,
    status,
    category: 'unknown',
  });
}

export function toApiErrorMessage(error: unknown, fallback = '请求未成功完成，请稍后重试。'): string {
  const parsed = getParsedApiError(error);
  const message = formatParsedApiError(parsed);
  return message.trim() || fallback;
}

export function isAxiosApiError(error: unknown): boolean {
  return axios.isAxiosError(error);
}
