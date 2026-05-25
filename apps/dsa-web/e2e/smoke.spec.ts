import { expect, test, type Page } from '@playwright/test';

const smokePassword = process.env.DSA_WEB_SMOKE_PASSWORD;

async function login(page: Page) {
  test.skip(!smokePassword, 'Set DSA_WEB_SMOKE_PASSWORD to run authenticated smoke tests.');

  await page.goto('/login');
  await page.waitForLoadState('domcontentloaded');

  const passwordInput = page.locator('#password');
  const submitButton = page.getByRole('button', { name: /작업대로 이동|설정 완료 후 로그인/ });
  const homeLink = page.getByRole('link', { name: '홈' });

  const isAlreadyAuthenticated =
    page.url().endsWith('/') ||
    await homeLink.isVisible({ timeout: 2_000 }).catch(() => false);

  if (isAlreadyAuthenticated) {
    await page.waitForLoadState('domcontentloaded');
    return;
  }

  await expect(passwordInput).toBeVisible({ timeout: 10_000 });
  await passwordInput.fill(smokePassword!);
  await expect(submitButton).toBeVisible();

  await Promise.all([
    page.waitForResponse(
      (response) => response.url().includes('/api/v1/auth/login') && response.status() === 200,
      { timeout: 15_000 },
    ),
    submitButton.click(),
  ]);

  await page.waitForURL('/', { timeout: 15_000 });
  await page.waitForLoadState('domcontentloaded');
  await page.waitForTimeout(1000);
}

test.describe('web smoke', () => {
  test('login page renders password form', async ({ page }) => {
    await page.goto('/login');
    await page.waitForLoadState('domcontentloaded');

    await expect(page.getByText('DAILY STOCK').first()).toBeVisible();
    await expect(page.getByText('Analysis Engine')).toBeVisible();
    await expect(page.locator('#password')).toBeVisible();
    await expect(page.getByRole('button', { name: /작업대로 이동|설정 완료 후 로그인/ })).toBeVisible();
  });

  test('home page shows analysis entry and history panel after login', async ({ page }) => {
    await login(page);

    const stockInput = page.getByPlaceholder('종목 코드나 이름을 입력하세요. 예: 005930.KS, AAPL');
    await expect(stockInput).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole('link', { name: '홈' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'AI 종목 상담' })).toBeVisible();
    await expect(page.getByText('분석 기록')).toBeVisible();

    await stockInput.fill('600519');
    const analyzeButton = page.getByRole('button', { name: '분석', exact: true });
    await expect(analyzeButton).toBeVisible();
  });

  test('chat page allows entering a question and starts a request', async ({ page }) => {
    await login(page);

    await page.getByRole('link', { name: 'AI 종목 상담' }).click();
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1000);

    await expect(page.getByTestId('chat-workspace')).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId('chat-session-list-scroll')).toBeVisible();
    await expect(page.getByTestId('chat-message-scroll')).toBeVisible();

    const input = page.getByPlaceholder(/분석 600519/);
    await expect(input).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('전략', { exact: true })).toBeVisible();

    const prompt = '600519 간단히 분석해 주세요';
    await input.fill(prompt);
    await page.getByRole('button', { name: '전송' }).click();

    await expect(page.locator('p').filter({ hasText: prompt }).last()).toBeVisible({ timeout: 5000 });
  });

  test('chat page uses accessible labels instead of native title attributes for key actions', async ({ page }) => {
    await login(page);

    await page.getByRole('link', { name: 'AI 종목 상담' }).click();
    await page.waitForLoadState('domcontentloaded');

    const sendButton = page.getByRole('button', { name: '전송' });
    const composer = page.getByPlaceholder(/분석 600519/);

    await expect(page.getByTestId('chat-workspace')).toBeVisible({ timeout: 10_000 });
    await expect(sendButton).toBeVisible({ timeout: 10_000 });
    await expect(composer).toBeVisible({ timeout: 10_000 });

    await expect(sendButton).not.toHaveAttribute('title', /.+/);
    await expect(composer).not.toHaveAttribute('title', /.+/);
  });

  test('mobile shell opens navigation drawer after login', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await login(page);

    const menuButton = page.getByRole('button', { name: /내비게이션 메뉴 열기|메뉴/ });
    if (await menuButton.isVisible({ timeout: 2000 }).catch(() => false)) {
      await menuButton.click();
    }

    await expect(page.getByRole('link', { name: '백테스트' })).toBeVisible({ timeout: 5000 });
  });

  test('settings page renders title and save actions after login', async ({ page }) => {
    await login(page);

    await page.getByRole('link', { name: '설정' }).click();
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1000);

    await expect(page.getByRole('heading', { name: '시스템 설정' })).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole('button', { name: '초기화' })).toBeVisible();
    await expect(page.getByRole('button', { name: /설정 저장/ })).toBeVisible();
  });

  test('backtest page renders filter controls after login', async ({ page }) => {
    await login(page);

    await page.getByRole('link', { name: '백테스트' }).click();
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1000);

    const filterInput = page.getByPlaceholder(/종목 코드 필터/);
    await expect(filterInput).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole('button', { name: '필터' })).toBeVisible();
    await expect(page.getByRole('button', { name: /백테스트 실행/ })).toBeVisible();
  });
});
