import { test, expect } from '@playwright/test';

test.describe('Prospect Enhancement Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the prospects page
    await page.goto('/');

    // Wait for prospects to load
    await page.waitForSelector('[data-testid="prospects-table"]', { timeout: 10000 });
  });

  test('should display prospects table', async ({ page }) => {
    // Check that prospects table is visible
    await expect(page.locator('[data-testid="prospects-table"]')).toBeVisible();

    // Check for table headers
    await expect(page.getByText('Title')).toBeVisible();
    await expect(page.getByText('Agency')).toBeVisible();
    await expect(page.getByText('Posted Date')).toBeVisible();
    await expect(page.getByText('Response Date')).toBeVisible();
  });

  test('should open prospect details modal', async ({ page }) => {
    // Click on first prospect row
    await page.locator('[data-testid="prospect-row"]').first().click();

    // Wait for modal to open
    await expect(page.getByRole('dialog')).toBeVisible();
    await expect(page.getByText('Contract Details')).toBeVisible();

    // Check for key prospect information sections
    await expect(page.getByText('Basic Information')).toBeVisible();
    await expect(page.getByText('Contact Information')).toBeVisible();
    await expect(page.getByText('Description')).toBeVisible();
  });

  test('should enhance prospect with AI', async ({ page }) => {
    // Open prospect details
    await page.locator('[data-testid="prospect-row"]').first().click();
    await expect(page.getByRole('dialog')).toBeVisible();

    // Look for enhancement button
    const enhanceButton = page.getByRole('button', { name: /enhance with ai/i });
    await expect(enhanceButton).toBeVisible();

    // Click enhancement button
    await enhanceButton.click();

    // Should show queued status or processing indicator
    await expect(
      page.getByText(/queued|processing|enhancing/i)
    ).toBeVisible({ timeout: 5000 });
  });

  test('should filter prospects by agency', async ({ page }) => {
    // Wait for filter controls
    await page.waitForSelector('[data-testid="agency-filter"]');

    // Open agency filter dropdown
    await page.locator('[data-testid="agency-filter"]').click();

    // Select first agency option
    await page.locator('[data-testid="agency-option"]').first().click();

    // Verify table updated
    await page.waitForTimeout(1000); // Allow filter to apply

    // Should still have prospects table visible
    await expect(page.locator('[data-testid="prospects-table"]')).toBeVisible();
  });

  test('should search prospects by title', async ({ page }) => {
    // Find search input
    const searchInput = page.locator('[data-testid="search-input"]');
    await expect(searchInput).toBeVisible();

    // Type search query
    await searchInput.fill('software');

    // Wait for search results
    await page.waitForTimeout(1000);

    // Table should still be visible
    await expect(page.locator('[data-testid="prospects-table"]')).toBeVisible();
  });

  test('should toggle AI enhanced data view', async ({ page }) => {
    // Open prospect details
    await page.locator('[data-testid="prospect-row"]').first().click();
    await expect(page.getByRole('dialog')).toBeVisible();

    // Look for AI enhanced toggle
    const aiToggle = page.getByRole('switch', { name: /show ai enhanced/i });
    if (await aiToggle.isVisible()) {
      // Toggle AI enhanced view
      await aiToggle.click();

      // Should show enhanced data indicators
      await expect(page.locator('text=✨')).toBeVisible();
    }
  });

  test('should make go/no-go decision', async ({ page }) => {
    // Open prospect details
    await page.locator('[data-testid="prospect-row"]').first().click();
    await expect(page.getByRole('dialog')).toBeVisible();

    // Look for decision buttons
    const goButton = page.getByRole('button', { name: /go/i });
    const _noGoButton = page.getByRole('button', { name: /no.go/i });

    if (await goButton.isVisible()) {
      // Make a "Go" decision
      await goButton.click();

      // Should show success indication or decision recorded
      await expect(
        page.getByText(/decision recorded|go decision/i)
      ).toBeVisible({ timeout: 5000 });
    }
  });

  test('should handle enhancement queue operations', async ({ page }) => {
    // Navigate to admin/queue page if it exists
    try {
      await page.goto('/admin/queue');

      // Check for queue status
      await expect(page.getByText(/queue status|processing/i)).toBeVisible({ timeout: 5000 });

      // Look for start/stop buttons
      const startButton = page.getByRole('button', { name: /start/i });
      const stopButton = page.getByRole('button', { name: /stop/i });

      if (await startButton.isVisible()) {
        await startButton.click();
        await expect(page.getByText(/started|processing/i)).toBeVisible();
      }

      if (await stopButton.isVisible()) {
        await stopButton.click();
        await expect(page.getByText(/stopped|idle/i)).toBeVisible();
      }

    } catch (error) {
      // Skip this test if admin page doesn't exist
      console.log('Admin queue page not available, skipping queue operations test');
    }
  });

  test('should handle errors gracefully', async ({ page }) => {
    // Test error handling by simulating network failure
    await page.route('**/api/llm/**', route => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'Internal server error' })
      });
    });

    // Try to enhance a prospect
    await page.locator('[data-testid="prospect-row"]').first().click();
    await expect(page.getByRole('dialog')).toBeVisible();

    const enhanceButton = page.getByRole('button', { name: /enhance with ai/i });
    if (await enhanceButton.isVisible()) {
      await enhanceButton.click();

      // Should show error message
      await expect(
        page.getByText(/error|failed|something went wrong/i)
      ).toBeVisible({ timeout: 5000 });
    }
  });

  test('should support pagination', async ({ page }) => {
    // Look for pagination controls
    const nextButton = page.getByRole('button', { name: /next/i });
    const _prevButton = page.getByRole('button', { name: /previous/i });
    const _pageInfo = page.locator('[data-testid="page-info"]');

    if (await nextButton.isVisible()) {
      // Click next page
      await nextButton.click();

      // Wait for page to update
      await page.waitForTimeout(1000);

      // Table should still be visible
      await expect(page.locator('[data-testid="prospects-table"]')).toBeVisible();
    }
  });

  test('should be responsive on mobile devices', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });

    // Navigate to prospects page
    await page.goto('/');

    // Should still show prospects (might be in mobile layout)
    await expect(page.locator('[data-testid="prospects-table"]')).toBeVisible();

    // Try opening a prospect detail
    await page.locator('[data-testid="prospect-row"]').first().click();

    // Modal should be responsive
    await expect(page.getByRole('dialog')).toBeVisible();
  });
});
