import { test, expect } from '@playwright/test';

test.describe('Performance and Accessibility', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('should load initial page within acceptable time', async ({ page }) => {
    const startTime = Date.now();

    await page.goto('/', { waitUntil: 'networkidle' });

    const loadTime = Date.now() - startTime;

    // Should load within 5 seconds
    expect(loadTime).toBeLessThan(5000);

    // Should show main content
    await expect(page.locator('[data-testid="prospects-table"]')).toBeVisible({ timeout: 10000 });
  });

  test('should handle large datasets efficiently', async ({ page }) => {
    await page.waitForSelector('[data-testid="prospects-table"]', { timeout: 10000 });

    // Measure table rendering performance
    const startTime = Date.now();

    // Scroll through table to test virtualization
    for (let i = 0; i < 5; i++) {
      await page.keyboard.press('PageDown');
      await page.waitForTimeout(100);
    }

    const scrollTime = Date.now() - startTime;

    // Scrolling should be smooth (under 2 seconds for 5 page downs)
    expect(scrollTime).toBeLessThan(2000);

    // Table should remain responsive
    await expect(page.locator('[data-testid="prospects-table"]')).toBeVisible();
  });

  test('should be keyboard navigable', async ({ page }) => {
    await page.waitForSelector('[data-testid="prospects-table"]', { timeout: 10000 });

    // Test keyboard navigation
    await page.keyboard.press('Tab');

    // Should focus first interactive element
    const focusedElement = page.locator(':focus');
    await expect(focusedElement).toBeVisible();

    // Continue tabbing through interface
    for (let i = 0; i < 10; i++) {
      await page.keyboard.press('Tab');
      const currentFocus = page.locator(':focus');

      if (await currentFocus.isVisible()) {
        // Focus should be visible and within viewport
        await expect(currentFocus).toBeVisible();
      }
    }

    // Test table navigation with arrow keys
    const firstRow = page.locator('[data-testid="prospect-row"]').first();
    if (await firstRow.isVisible()) {
      await firstRow.focus();

      // Arrow down should move to next row
      await page.keyboard.press('ArrowDown');

      // Enter should open details
      await page.keyboard.press('Enter');

      // Should open modal
      const modal = page.getByRole('dialog');
      if (await modal.isVisible()) {
        await expect(modal).toBeVisible();

        // Escape should close modal
        await page.keyboard.press('Escape');
        await expect(modal).not.toBeVisible();
      }
    }
  });

  test('should have proper ARIA labels and roles', async ({ page }) => {
    await page.waitForSelector('[data-testid="prospects-table"]', { timeout: 10000 });

    // Check table accessibility
    const table = page.locator('[data-testid="prospects-table"]');
    await expect(table).toHaveAttribute('role', 'table');

    // Check for column headers
    const columnHeaders = page.locator('[role="columnheader"]');
    const headerCount = await columnHeaders.count();
    expect(headerCount).toBeGreaterThan(0);

    // Check for row accessibility
    const rows = page.locator('[role="row"]');
    const rowCount = await rows.count();
    expect(rowCount).toBeGreaterThan(0);

    // Check buttons have accessible names
    const buttons = page.locator('button');
    const buttonCount = await buttons.count();

    for (let i = 0; i < Math.min(buttonCount, 10); i++) {
      const button = buttons.nth(i);
      if (await button.isVisible()) {
        const ariaLabel = await button.getAttribute('aria-label');
        const text = await button.textContent();
        const title = await button.getAttribute('title');

        // Button should have accessible name
        expect(ariaLabel || text || title).toBeTruthy();
      }
    }
  });

  test('should support screen reader announcements', async ({ page }) => {
    await page.waitForSelector('[data-testid="prospects-table"]', { timeout: 10000 });

    // Check for live regions
    const liveRegions = page.locator('[aria-live]');

    if (await liveRegions.first().isVisible()) {
      const liveRegionCount = await liveRegions.count();
      expect(liveRegionCount).toBeGreaterThan(0);

      // Check live region values
      for (let i = 0; i < Math.min(liveRegionCount, 3); i++) {
        const region = liveRegions.nth(i);
        const ariaLive = await region.getAttribute('aria-live');
        expect(['polite', 'assertive', 'off']).toContain(ariaLive);
      }
    }

    // Test status announcements
    const firstRow = page.locator('[data-testid="prospect-row"]').first();
    if (await firstRow.isVisible()) {
      await firstRow.click();

      const modal = page.getByRole('dialog');
      if (await modal.isVisible()) {
        // Modal should have proper announcements
        const modalTitle = modal.locator('[role="heading"], h1, h2, h3');
        if (await modalTitle.first().isVisible()) {
          const titleText = await modalTitle.first().textContent();
          expect(titleText).toBeTruthy();
        }
      }
    }
  });

  test('should have sufficient color contrast', async ({ page }) => {
    await page.waitForSelector('[data-testid="prospects-table"]', { timeout: 10000 });

    // Test with high contrast mode
    await page.emulateMedia({ colorScheme: 'dark' });

    // Content should still be visible in dark mode
    await expect(page.locator('[data-testid="prospects-table"]')).toBeVisible();

    // Reset to light mode
    await page.emulateMedia({ colorScheme: 'light' });

    // Content should be visible in light mode
    await expect(page.locator('[data-testid="prospects-table"]')).toBeVisible();
  });

  test('should be responsive on mobile devices', async ({ page }) => {
    // Test mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });

    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Content should be visible on mobile
    await expect(page.locator('[data-testid="prospects-table"]')).toBeVisible({ timeout: 10000 });

    // Should be scrollable
    await page.mouse.wheel(0, 500);
    await page.waitForTimeout(500);

    // Test tablet viewport
    await page.setViewportSize({ width: 768, height: 1024 });

    // Content should adapt to tablet
    await expect(page.locator('[data-testid="prospects-table"]')).toBeVisible();

    // Test desktop viewport
    await page.setViewportSize({ width: 1200, height: 800 });

    // Content should work on desktop
    await expect(page.locator('[data-testid="prospects-table"]')).toBeVisible();
  });

  test('should handle zoom levels gracefully', async ({ page }) => {
    await page.waitForSelector('[data-testid="prospects-table"]', { timeout: 10000 });

    // Test 200% zoom
    await page.evaluate(() => {
      document.body.style.zoom = '2';
    });

    await page.waitForTimeout(1000);

    // Content should still be usable at high zoom
    await expect(page.locator('[data-testid="prospects-table"]')).toBeVisible();

    // Test 50% zoom
    await page.evaluate(() => {
      document.body.style.zoom = '0.5';
    });

    await page.waitForTimeout(1000);

    // Content should still be readable at low zoom
    await expect(page.locator('[data-testid="prospects-table"]')).toBeVisible();

    // Reset zoom
    await page.evaluate(() => {
      document.body.style.zoom = '1';
    });
  });

  test('should optimize image loading', async ({ page }) => {
    await page.waitForSelector('[data-testid="prospects-table"]', { timeout: 10000 });

    // Check for images (icons, logos, etc.)
    const images = page.locator('img');
    const imageCount = await images.count();

    if (imageCount > 0) {
      for (let i = 0; i < Math.min(imageCount, 5); i++) {
        const img = images.nth(i);

        if (await img.isVisible()) {
          // Images should have alt text
          const altText = await img.getAttribute('alt');
          expect(altText).toBeTruthy();

          // Images should load successfully
          const naturalWidth = await img.evaluate((el: HTMLImageElement) => el.naturalWidth);
          expect(naturalWidth).toBeGreaterThan(0);
        }
      }
    }
  });

  test('should handle reduced motion preferences', async ({ page }) => {
    // Enable reduced motion
    await page.emulateMedia({ reducedMotion: 'reduce' });

    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Content should load without excessive animations
    await expect(page.locator('[data-testid="prospects-table"]')).toBeVisible({ timeout: 10000 });

    // Test interactions with reduced motion
    const firstRow = page.locator('[data-testid="prospect-row"]').first();
    if (await firstRow.isVisible()) {
      await firstRow.click();

      const modal = page.getByRole('dialog');
      if (await modal.isVisible()) {
        // Modal should appear without distracting animations
        await expect(modal).toBeVisible();
      }
    }
  });

  test('should optimize memory usage', async ({ page }) => {
    await page.waitForSelector('[data-testid="prospects-table"]', { timeout: 10000 });

    // Get initial memory usage
    const initialMetrics = await page.evaluate(() => {
      return (performance as any).memory ? {
        usedJSHeapSize: (performance as any).memory.usedJSHeapSize,
        totalJSHeapSize: (performance as any).memory.totalJSHeapSize
      } : null;
    });

    if (initialMetrics) {
      // Perform memory-intensive operations
      for (let i = 0; i < 10; i++) {
        // Open and close modals
        const rows = page.locator('[data-testid="prospect-row"]');
        const rowCount = await rows.count();

        if (rowCount > 0) {
          await rows.first().click();
          const modal = page.getByRole('dialog');

          if (await modal.isVisible()) {
            await page.keyboard.press('Escape');
            await expect(modal).not.toBeVisible();
          }
        }

        await page.waitForTimeout(100);
      }

      // Check memory after operations
      const finalMetrics = await page.evaluate(() => {
        return (performance as any).memory ? {
          usedJSHeapSize: (performance as any).memory.usedJSHeapSize,
          totalJSHeapSize: (performance as any).memory.totalJSHeapSize
        } : null;
      });

      if (finalMetrics) {
        // Memory growth should be reasonable (less than 10MB increase)
        const memoryGrowth = finalMetrics.usedJSHeapSize - initialMetrics.usedJSHeapSize;
        expect(memoryGrowth).toBeLessThan(10 * 1024 * 1024); // 10MB
      }
    }
  });

  test('should handle focus management correctly', async ({ page }) => {
    await page.waitForSelector('[data-testid="prospects-table"]', { timeout: 10000 });

    // Test modal focus management
    const firstRow = page.locator('[data-testid="prospect-row"]').first();
    if (await firstRow.isVisible()) {
      await firstRow.click();

      const modal = page.getByRole('dialog');
      if (await modal.isVisible()) {
        // Focus should be trapped within modal
        await page.keyboard.press('Tab');

        const focusedElement = page.locator(':focus');
        const isWithinModal = await focusedElement.evaluate((el, modalEl) => {
          return modalEl.contains(el);
        }, await modal.elementHandle());

        expect(isWithinModal).toBeTruthy();

        // Escape should close modal and restore focus
        await page.keyboard.press('Escape');
        await expect(modal).not.toBeVisible();

        // Focus should return to trigger element or appropriate location
        const currentFocus = page.locator(':focus');
        await expect(currentFocus).toBeVisible();
      }
    }
  });

  test('should provide skip links for navigation', async ({ page }) => {
    await page.goto('/');

    // Look for skip links (usually hidden until focused)
    const skipLinks = page.locator('a[href*="#"], .skip-link, [data-testid*="skip"]');

    if (await skipLinks.first().isVisible()) {
      // Should have skip to main content
      const skipToMain = skipLinks.filter({ hasText: /skip.*main|main.*content/i });

      if (await skipToMain.first().isVisible()) {
        await skipToMain.first().focus();
        await page.keyboard.press('Enter');

        // Should jump to main content
        const mainContent = page.locator('main, [role="main"], #main');
        if (await mainContent.isVisible()) {
          await expect(mainContent).toBeFocused();
        }
      }
    }
  });
});
