import { expect, test, type Page } from '@playwright/test';

const smokePassword = process.env.DSA_WEB_SMOKE_PASSWORD;
const stockInputPlaceholder = '종목 코드나 이름을 입력하세요. 예: 005930.KS, AAPL';

async function login(page: Page) {
  test.skip(!smokePassword, 'Set DSA_WEB_SMOKE_PASSWORD to run report markdown tests.');

  await page.goto('/login');
  await page.waitForLoadState('domcontentloaded');

  await expect(page.locator('#password')).toBeVisible({ timeout: 10_000 });
  await page.locator('#password').fill(smokePassword!);

  const submitButton = page.getByRole('button', { name: /작업대로 이동|설정 완료 후 로그인/ });
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
  await expect(page.getByPlaceholder(stockInputPlaceholder)).toBeVisible({ timeout: 10_000 });
}

async function openFirstReportDrawer(page: Page) {
  await page.getByRole('link', { name: '홈' }).click();
  await page.waitForLoadState('domcontentloaded');
  await expect(page.getByText('분석 기록')).toBeVisible({ timeout: 10_000 });

  const firstHistoryItem = page.locator('.home-history-item').first();
  await expect(firstHistoryItem).toBeVisible({ timeout: 10_000 });
  await firstHistoryItem.click();

  const detailedReportButton = page.getByRole('button', { name: '전체 분석 리포트' });
  await expect(detailedReportButton).toBeEnabled({ timeout: 3000 });
  await detailedReportButton.click();

  await expect(page.getByRole('dialog').getByText('전체 분석 리포트')).toBeVisible({ timeout: 10_000 });
}

test.describe('ReportMarkdown component', () => {
  test('copy markdown source code', async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await login(page);
    await openFirstReportDrawer(page);

    const copyMarkdownButton = page.getByRole('button', { name: 'Markdown 원문 복사' });
    await expect(copyMarkdownButton).toBeVisible({ timeout: 5000 });
    await copyMarkdownButton.click();

    const clipboardText = await page.evaluate(() => navigator.clipboard.readText());
    expect(clipboardText).toBeTruthy();
    expect(clipboardText.length).toBeGreaterThan(0);

    const checkmarkIcon = page.locator('button[aria-label="Markdown 원문 복사"] svg.text-success');
    await expect(checkmarkIcon).toBeVisible();
    await expect(checkmarkIcon).not.toBeVisible({ timeout: 3500 });
  });

  test('copy plain text', async ({ page, context }) => {
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await login(page);
    await openFirstReportDrawer(page);

    const copyPlainTextButton = page.getByRole('button', { name: '일반 텍스트 복사' });
    await expect(copyPlainTextButton).toBeVisible({ timeout: 5000 });
    await copyPlainTextButton.click();

    const clipboardText = await page.evaluate(() => navigator.clipboard.readText());
    expect(clipboardText).toBeTruthy();
    expect(clipboardText.length).toBeGreaterThan(0);
    expect(clipboardText).not.toMatch(/^#{1,6}\s+/m);
    expect(clipboardText).not.toMatch(/\*\*[^*]+\*\*/);

    const lines = clipboardText.split('\n');
    const hasTableSeparators = lines.some((line) =>
      line.match(/^\|[\s|:-]+\|$/) || line.match(/^[\s|:-]+$/),
    );
    expect(hasTableSeparators).toBeFalsy();

    const checkmarkIcon = page.locator('button[aria-label="일반 텍스트 복사"] svg.text-success');
    await expect(checkmarkIcon).toBeVisible();
    await expect(checkmarkIcon).not.toBeVisible({ timeout: 3500 });
  });

  test('mobile responsive layout', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await login(page);

    await expect(page.getByPlaceholder(stockInputPlaceholder)).toBeVisible({ timeout: 10_000 });

    const detailedReportButton = page.getByRole('button', { name: '전체 분석 리포트' });
    await expect(detailedReportButton).toBeVisible({ timeout: 5000 });
    await detailedReportButton.click();

    await expect(page.getByRole('dialog').getByText('전체 분석 리포트')).toBeVisible({ timeout: 10_000 });

    const copyMarkdownButton = page.getByRole('button', { name: 'Markdown 원문 복사' });
    const copyPlainTextButton = page.getByRole('button', { name: '일반 텍스트 복사' });

    await expect(copyMarkdownButton).toBeVisible({ timeout: 5000 });
    await expect(copyPlainTextButton).toBeVisible();
    await expect(copyMarkdownButton).toBeEnabled();
    await expect(copyPlainTextButton).toBeEnabled();
  });

  test('buttons are enabled after report content loads', async ({ page }) => {
    await login(page);
    await openFirstReportDrawer(page);

    const copyMarkdownButton = page.getByRole('button', { name: 'Markdown 원문 복사' });
    const copyPlainTextButton = page.getByRole('button', { name: '일반 텍스트 복사' });

    await expect(copyMarkdownButton).toBeVisible({ timeout: 5000 });
    await expect(copyPlainTextButton).toBeVisible();
    await expect(copyMarkdownButton).toBeEnabled({ timeout: 5000 });

    const isMarkdownEnabled = await copyMarkdownButton.isEnabled();
    const isPlainTextEnabled = await copyPlainTextButton.isEnabled();
    expect(isMarkdownEnabled || isPlainTextEnabled).toBeTruthy();
  });
});
