import { afterEach, describe, expect, it } from 'vitest';
import { buildLoginPath, buildRegistrationPath } from '../useProductSurface';

describe('useProductSurface locale-aware auth paths', () => {
  afterEach(() => {
    window.history.replaceState(window.history.state, '', '/');
    window.localStorage.clear();
  });

  it('builds locale-prefixed login paths from the active route surface', () => {
    window.history.replaceState(window.history.state, '', '/en/chat');

    expect(buildLoginPath('/chat')).toBe('/en/login?redirect=%2Fen%2Fchat');
  });

  it('builds locale-prefixed registration paths from the stored locale when the route is unprefixed', () => {
    window.localStorage.setItem('dsa-ui-language', 'zh');
    window.history.replaceState(window.history.state, '', '/settings');

    expect(buildRegistrationPath('/settings')).toBe('/zh/login?mode=create&redirect=%2Fzh%2Fsettings');
  });
});
