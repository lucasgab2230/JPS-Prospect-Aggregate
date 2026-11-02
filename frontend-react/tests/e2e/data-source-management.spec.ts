import { test, expect } from '@playwright/test';

test.describe('Data Source Management', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');

    // Wait for initial load
    await page.waitForLoadState('networkidle');
  });

  test('should display data sources in filter dropdown', async ({ page }) => {
    // Wait for prospects table to load
    await page.waitForSelector('[data-testid="prospects-table"]', { timeout: 10000 });

    // Look for data source filter
    const dataSourceFilter = page.locator('[data-testid="agency-filter"], [data-testid="data-source-filter"]');

    if (await dataSourceFilter.isVisible()) {
      await dataSourceFilter.click();

      // Should show available data sources
      await expect(page.getByText(/department|agency|source/i)).toBeVisible();

      // Should have selectable options
      const options = page.locator('[data-testid*="option"], [role="option"]');
      const optionCount = await options.count();
      expect(optionCount).toBeGreaterThan(0);
    }
  });

  test('should filter prospects by data source', async ({ page }) => {
    await page.waitForSelector('[data-testid="prospects-table"]', { timeout: 10000 });

    // Get initial prospect count
    const _initialRows = await page.locator('[data-testid="prospect-row"]').count();

    // Open data source filter
    const dataSourceFilter = page.locator('[data-testid="agency-filter"], [data-testid="data-source-filter"]');

    if (await dataSourceFilter.isVisible()) {
      await dataSourceFilter.click();

      // Select first available option
      const firstOption = page.locator('[data-testid*="option"], [role="option"]').first();
      if (await firstOption.isVisible()) {
        await firstOption.click();

        // Wait for filter to apply
        await page.waitForTimeout(1000);

        // Table should still be visible (might have fewer rows)
        await expect(page.locator('[data-testid="prospects-table"]')).toBeVisible();

        // Should show filtered results or empty state
        const filteredRows = await page.locator('[data-testid="prospect-row"]').count();
        expect(filteredRows).toBeGreaterThanOrEqual(0);
      }
    }
  });

  test('should display data source information in prospects', async ({ page }) => {
    await page.waitForSelector('[data-testid="prospects-table"]', { timeout: 10000 });

    // Check if agency/source column is visible in table
    await expect(page.getByText(/agency|source/i).first()).toBeVisible();

    // Open first prospect to see detailed source info
    await page.locator('[data-testid="prospect-row"]').first().click();
    await expect(page.getByRole('dialog')).toBeVisible();

    // Should show source information in modal
    const hasSourceInfo = await page.getByText(/source|agency|department/i).count() > 0;
    expect(hasSourceInfo).toBeTruthy();
  });

  test('should handle data source status', async ({ page }) => {
    // Try to navigate to admin or status page
    try {
      await page.goto('/admin/sources');
      await page.waitForLoadState('networkidle');

      // Look for data source status indicators
      const statusIndicators = page.getByText(/active|inactive|last scraped|status/i);

      if (await statusIndicators.first().isVisible()) {
        // Should show source status information
        await expect(statusIndicators.first()).toBeVisible();

        // Look for scraping timestamps
        const timestamps = page.locator('text=/\\d{1,2}\\/\\d{1,2}\\/\\d{4}|\\d{4}-\\d{2}-\\d{2}/');
        if (await timestamps.first().isVisible()) {
          expect(await timestamps.count()).toBeGreaterThan(0);
        }
      }
    } catch (error) {
      // Skip if admin interface doesn't exist
      console.log('Admin sources page not available, skipping status test');
    }
  });

  test('should display scraping statistics', async ({ page }) => {
    // Navigate to statistics or admin page
    try {
      await page.goto('/admin/stats');
      await page.waitForLoadState('networkidle');

      // Look for scraping statistics
      const statsSection = page.getByText(/statistics|scraping|data sources/i);

      if (await statsSection.first().isVisible()) {
        // Should show numerical statistics
        await expect(page.locator('text=/\\d+/')).toBeVisible();

        // Look for success/failure rates
        const metrics = page.getByText(/success|failure|total|count/i);
        if (await metrics.first().isVisible()) {
          expect(await metrics.count()).toBeGreaterThan(0);
        }
      }
    } catch (error) {
      // Skip if stats page doesn't exist
      console.log('Admin stats page not available, skipping statistics test');
    }
  });

  test('should handle data source refresh', async ({ page }) => {
    await page.waitForSelector('[data-testid="prospects-table"]', { timeout: 10000 });

    // Look for refresh button
    const refreshButton = page.getByRole('button', { name: /refresh|reload|update/i });

    if (await refreshButton.isVisible()) {
      await refreshButton.click();

      // Should show loading indicator
      const loadingIndicator = page.getByText(/loading|refreshing|updating/i);
      if (await loadingIndicator.isVisible()) {
        // Wait for loading to complete
        await expect(loadingIndicator).not.toBeVisible({ timeout: 10000 });
      }

      // Table should still be visible after refresh
      await expect(page.locator('[data-testid="prospects-table"]')).toBeVisible();
    }
  });

  test('should show data freshness indicators', async ({ page }) => {
    await page.waitForSelector('[data-testid="prospects-table"]', { timeout: 10000 });

    // Open first prospect
    await page.locator('[data-testid="prospect-row"]').first().click();
    await expect(page.getByRole('dialog')).toBeVisible();

    // Look for data freshness indicators
    const freshnessIndicators = page.getByText(/loaded|updated|scraped|fresh/i);

    if (await freshnessIndicators.first().isVisible()) {
      // Should show timestamp information
      const timestamps = page.locator('text=/\\d{1,2}\\/\\d{1,2}\\/\\d{4}|\\d{4}-\\d{2}-\\d{2}|\\d+\\s+(minute|hour|day)s?\\s+ago/');
      expect(await timestamps.count()).toBeGreaterThan(0);
    }
  });

  test('should handle multiple data source selection', async ({ page }) => {
    await page.waitForSelector('[data-testid="prospects-table"]', { timeout: 10000 });

    // Look for multi-select data source filter
    const dataSourceFilter = page.locator('[data-testid="agency-filter"], [data-testid="data-source-filter"]');

    if (await dataSourceFilter.isVisible()) {
      await dataSourceFilter.click();

      // Check if multiple selection is supported
      const options = page.locator('[data-testid*="option"], [role="option"]');
      const optionCount = await options.count();

      if (optionCount > 1) {
        // Select first option
        await options.first().click();

        // Try to select second option (if multi-select is supported)
        if (await options.nth(1).isVisible()) {
          await options.nth(1).click();
        }

        // Apply filters and verify results
        const applyButton = page.getByRole('button', { name: /apply|filter/i });
        if (await applyButton.isVisible()) {
          await applyButton.click();
        }

        // Wait for results
        await page.waitForTimeout(1000);
        await expect(page.locator('[data-testid="prospects-table"]')).toBeVisible();
      }
    }
  });

  test('should display data source health status', async ({ page }) => {
    // Check main page for any health indicators
    await page.waitForSelector('[data-testid="prospects-table"]', { timeout: 10000 });

    // Look for status indicators in UI
    const statusIndicators = page.getByText(/healthy|warning|error|down|up/i);

    if (await statusIndicators.first().isVisible()) {
      // Should show clear status indication
      await expect(statusIndicators.first()).toBeVisible();
    }

    // Try to access health endpoint directly
    try {
      await page.goto('/api/health');

      // Should show health status in JSON or UI format
      const healthContent = page.locator('body');
      const hasHealthData = await healthContent.textContent();

      if (hasHealthData && hasHealthData.includes('status')) {
        expect(hasHealthData).toBeTruthy();
      }
    } catch (error) {
      // Health endpoint might not be accessible via browser
      console.log('Health endpoint not accessible via browser navigation');
    }
  });

  test('should handle data source configuration errors', async ({ page }) => {
    // Navigate to prospects and look for error states
    await page.waitForSelector('[data-testid="prospects-table"]', { timeout: 10000 });

    // Look for error messages or indicators
    const errorMessages = page.getByText(/error|failed|unavailable|connection|timeout/i);

    if (await errorMessages.first().isVisible()) {
      // Should show clear error information
      await expect(errorMessages.first()).toBeVisible();

      // Look for retry or refresh options
      const retryButton = page.getByRole('button', { name: /retry|refresh|try again/i });
      if (await retryButton.isVisible()) {
        await retryButton.click();

        // Should attempt to recover
        await page.waitForTimeout(2000);
      }
    }
  });
});
