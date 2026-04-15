import { describe, expect, it } from 'vitest';
import { parseApiError } from '../error';

describe('parseApiError', () => {
  it('classifies login-required responses as auth-required guidance', () => {
    const parsed = parseApiError({
      response: {
        status: 401,
        data: {
          detail: {
            error: 'unauthorized',
            message: 'Login required',
          },
        },
      },
    });

    expect(parsed.category).toBe('auth_required');
    expect(parsed.title).toBe('需要登录');
  });

  it('classifies admin unlock errors without pretending they are upstream provider failures', () => {
    const parsed = parseApiError({
      response: {
        status: 403,
        data: {
          detail: {
            error: 'admin_unlock_required',
            message: 'Admin settings are locked. Verify admin password to continue.',
          },
        },
      },
    });

    expect(parsed.category).toBe('admin_unlock_required');
    expect(parsed.title).toBe('管理员验证已过期');
  });

  it('classifies owner mismatch responses as access-denied app errors', () => {
    const parsed = parseApiError({
      response: {
        status: 403,
        data: {
          detail: {
            error: 'owner_mismatch',
            message: 'The requested owner_id does not match the current user',
          },
        },
      },
    });

    expect(parsed.category).toBe('access_denied');
    expect(parsed.title).toBe('无法访问其他用户的数据');
  });

  it('classifies IBKR session-expired responses as bounded validation guidance', () => {
    const parsed = parseApiError({
      response: {
        status: 400,
        data: {
          detail: {
            error: 'ibkr_session_expired',
            message: '当前 IBKR session 已失效、未授权或未连上可访问账户。',
          },
        },
      },
    });

    expect(parsed.category).toBe('validation_error');
    expect(parsed.title).toBe('IBKR 会话不可用');
  });

  it('classifies IBKR account mapping conflicts without treating them as generic upstream failures', () => {
    const parsed = parseApiError({
      response: {
        status: 409,
        data: {
          detail: {
            error: 'ibkr_account_mapping_conflict',
            message: '该 broker account ref 已绑定到当前用户的另一持仓账户。',
          },
        },
      },
    });

    expect(parsed.category).toBe('validation_error');
    expect(parsed.title).toBe('IBKR 账户映射冲突');
  });
});
