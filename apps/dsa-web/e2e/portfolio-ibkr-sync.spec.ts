import { expect, test } from '@playwright/test';

test('portfolio IBKR sync happy path keeps the result visible after metadata refresh', async ({ page }) => {
  let brokerConnectionsRequestCount = 0;
  let syncCompleted = false;

  const snapshotBase = {
    as_of: '2026-04-15',
    cost_method: 'fifo',
    currency: 'USD',
    account_count: 1,
    realized_pnl: 0,
    unrealized_pnl: 0,
    fee_total: 0,
    tax_total: 0,
    fx_stale: false,
  };

  const initialSnapshot = {
    ...snapshotBase,
    total_cash: 1000,
    total_market_value: 2000,
    total_equity: 3000,
    accounts: [
      {
        account_id: 1,
        account_name: 'Main',
        owner_id: 'user-1',
        broker: 'IBKR',
        market: 'us',
        base_currency: 'USD',
        as_of: '2026-04-15',
        cost_method: 'fifo',
        total_cash: 1000,
        total_market_value: 2000,
        total_equity: 3000,
        realized_pnl: 0,
        unrealized_pnl: 0,
        fee_total: 0,
        tax_total: 0,
        fx_stale: false,
        positions: [],
      },
    ],
  };

  const syncedSnapshot = {
    ...snapshotBase,
    total_cash: 5000,
    total_market_value: 1600,
    total_equity: 6600,
    unrealized_pnl: 100,
    accounts: [
      {
        account_id: 1,
        account_name: 'Main',
        owner_id: 'user-1',
        broker: 'IBKR',
        market: 'us',
        base_currency: 'USD',
        as_of: '2026-04-15',
        cost_method: 'fifo',
        total_cash: 5000,
        total_market_value: 1600,
        total_equity: 6600,
        realized_pnl: 0,
        unrealized_pnl: 100,
        fee_total: 0,
        tax_total: 0,
        fx_stale: false,
        positions: [
          {
            symbol: 'AAPL',
            market: 'us',
            currency: 'USD',
            quantity: 10,
            avg_cost: 150,
            total_cost: 1500,
            last_price: 160,
            market_value_base: 1600,
            unrealized_pnl_base: 100,
            valuation_currency: 'USD',
          },
        ],
      },
    ],
  };

  const riskPayload = {
    as_of: '2026-04-15',
    account_id: null,
    cost_method: 'fifo',
    currency: 'USD',
    thresholds: {},
    concentration: {
      total_market_value: syncCompleted ? 1600 : 0,
      top_weight_pct: syncCompleted ? 100 : 0,
      alert: false,
      top_positions: syncCompleted
        ? [{ symbol: 'AAPL', market_value_base: 1600, weight_pct: 100, is_alert: false }]
        : [],
    },
    sector_concentration: {
      total_market_value: 0,
      top_weight_pct: 0,
      alert: false,
      top_sectors: [],
      coverage: {},
      errors: [],
    },
    drawdown: {
      series_points: 0,
      max_drawdown_pct: 0,
      current_drawdown_pct: 0,
      alert: false,
      fx_stale: false,
    },
    stop_loss: {
      near_alert: false,
      triggered_count: 0,
      near_count: 0,
      items: [],
    },
  };

  await page.route('**/api/v1/auth/status', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        authEnabled: true,
        loggedIn: true,
        passwordSet: true,
        passwordChangeable: true,
        setupState: 'enabled',
        currentUser: {
          id: 'user-1',
          username: 'wolfy-user',
          displayName: 'Wolfy User',
          role: 'user',
          isAdmin: false,
          isAuthenticated: true,
          transitional: false,
          authEnabled: true,
        },
      }),
    });
  });

  await page.route('**/api/v1/portfolio/accounts**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        accounts: [
          {
            id: 1,
            owner_id: 'user-1',
            name: 'Main',
            broker: 'IBKR',
            market: 'us',
            base_currency: 'USD',
            is_active: true,
            created_at: '2026-04-15T09:00:00',
            updated_at: '2026-04-15T09:00:00',
          },
        ],
      }),
    });
  });

  await page.route('**/api/v1/portfolio/imports/brokers', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        brokers: [
          { broker: 'huatai', aliases: [], display_name: '华泰', file_extensions: ['csv'] },
          { broker: 'ibkr', aliases: ['interactivebrokers'], display_name: 'Interactive Brokers', file_extensions: ['xml'] },
        ],
      }),
    });
  });

  await page.route('**/api/v1/portfolio/broker-connections**', async (route) => {
    brokerConnectionsRequestCount += 1;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        connections: [
          {
            id: 9,
            owner_id: 'user-1',
            portfolio_account_id: 1,
            portfolio_account_name: 'Main',
            connection_name: 'Primary IBKR',
            broker_type: 'ibkr',
            broker_account_ref: 'U1234567',
            import_mode: syncCompleted ? 'api' : 'file',
            status: 'active',
            sync_metadata: {
              ibkr_api: {
                api_base_url: 'https://localhost:5000/v1/api',
                verify_ssl: false,
                broker_account_ref: 'U1234567',
              },
              last_sync_at: syncCompleted ? '2026-04-15T10:00:00' : null,
            },
          },
        ],
      }),
    });
  });

  await page.route('**/api/v1/portfolio/snapshot**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(syncCompleted ? syncedSnapshot : initialSnapshot),
    });
  });

  await page.route('**/api/v1/portfolio/risk**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(riskPayload),
    });
  });

  await page.route('**/api/v1/portfolio/trades**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: [], total: 0, page: 1, page_size: 20 }),
    });
  });

  await page.route('**/api/v1/portfolio/cash-ledger**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: [], total: 0, page: 1, page_size: 20 }),
    });
  });

  await page.route('**/api/v1/portfolio/corporate-actions**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: [], total: 0, page: 1, page_size: 20 }),
    });
  });

  await page.route('**/api/v1/portfolio/sync/ibkr', async (route) => {
    syncCompleted = true;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        account_id: 1,
        broker_connection_id: 9,
        broker_account_ref: 'U1234567',
        connection_name: 'Primary IBKR',
        snapshot_date: '2026-04-15',
        synced_at: '2026-04-15T10:00:00',
        base_currency: 'USD',
        total_cash: 5000,
        total_market_value: 1600,
        total_equity: 6600,
        realized_pnl: 0,
        unrealized_pnl: 100,
        position_count: 1,
        cash_balance_count: 1,
        fx_stale: false,
        snapshot_overlay_active: true,
        used_existing_connection: true,
        api_base_url: 'https://localhost:5000/v1/api',
        verify_ssl: false,
        warnings: [],
      }),
    });
  });

  await page.goto('/portfolio');
  await page.waitForLoadState('domcontentloaded');
  await expect(page.getByRole('heading', { name: '持仓管理' })).toBeVisible();

  const selects = page.locator('select');
  await selects.nth(0).selectOption('1');
  await expect.poll(() => brokerConnectionsRequestCount).toBeGreaterThanOrEqual(1);

  const brokerSelect = selects.nth(2);
  await brokerSelect.selectOption('ibkr');
  await expect(brokerSelect).toHaveValue('ibkr');

  await page.getByPlaceholder('IBKR Session Token（本次手动同步使用，不保存）').fill('session-token-123');
  await page.getByRole('button', { name: '只读同步 IBKR' }).click();

  await expect.poll(() => brokerConnectionsRequestCount).toBeGreaterThanOrEqual(2);
  await expect(brokerSelect).toHaveValue('ibkr');
  await expect(page.locator('body')).toContainText('当前日期快照已切换到 API 同步视图');
  await expect(page.locator('body')).toContainText('Ref: U1234567');
  await expect(page.locator('body')).toContainText('USD 6,600.00');
  await expect(page.locator('body')).toContainText('AAPL');
});
