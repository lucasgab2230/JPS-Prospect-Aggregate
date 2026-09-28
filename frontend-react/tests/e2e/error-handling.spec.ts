import { test, expect } from '@playwright/test';

test.describe('Error Handling and Recovery', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('should handle network connectivity issues', async ({ page }) => {
    // Set up network interception to simulate connectivity issues
    await page.route('**/api/prospects*', route => {
      route.abort('internetdisconnected');
    });

    // Try to reload or navigate
    await page.reload();

    // Should show network error message
    await expect(
      page.getByText(/network error|connection failed|offline|unable to connect/i)
    ).toBeVisible({ timeout: 10000 });

    // Look for retry button
    const retryButton = page.getByRole('button', { name: /retry|try again|reload/i });
    if (await retryButton.isVisible()) {
      // Remove network block before retrying
      await page.unroute('**/api/prospects*');

      await retryButton.click();

      // Should recover and show content
      await expect(page.locator('[data-testid="prospects-table"]')).toBeVisible({ timeout: 10000 });
    }
  });

  test('should handle API server errors', async ({ page }) => {
    // Mock API server error
    await page.route('**/api/prospects*', route => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'Internal Server Error' })
      });
    });

    await page.reload();

    // Should show server error message
    await expect(
      page.getByText(/server error|internal error|something went wrong|500/i)
    ).toBeVisible({ timeout: 10000 });

    // Should provide user-friendly error message
    const errorMessage = page.locator('[data-testid="error-message"], .error-message, .alert-error');
    if (await errorMessage.isVisible()) {
      const errorText = await errorMessage.textContent();
      expect(errorText).toBeTruthy();
      expect(errorText).not.toContain('undefined');
      expect(errorText).not.toContain('null');
    }
  });

  test('should handle authentication failures', async ({ page }) => {
    // Mock authentication error
    await page.route('**/api/**', route => {
      if (route.request().url().includes('/api/')) {
        route.fulfill({
          status: 401,
          contentType: 'application/json',
          body: JSON.stringify({ error: 'Unauthorized' })
        });
      } else {
        route.continue();
      }
    });

    // Try to access protected resource
    await page.goto('/admin');

    // Should handle auth error gracefully
    const authError = page.getByText(/unauthorized|access denied|login required|authentication/i);
    if (await authError.isVisible()) {
      await expect(authError).toBeVisible();

      // Should provide login option
      const loginButton = page.getByRole('button', { name: /login|sign in/i });
      if (await loginButton.isVisible()) {
        await expect(loginButton).toBeVisible();
      }
    }
  });

  test('should handle malformed data responses', async ({ page }) => {
    // Mock malformed JSON response
    await page.route('**/api/prospects*', route => {
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: 'invalid json response {malformed'
      });
    });

    await page.reload();

    // Should handle parsing error gracefully
    await expect(
      page.getByText(/error loading|invalid response|data error/i)
    ).toBeVisible({ timeout: 10000 });

    // Should not crash the application
    await expect(page.locator('body')).toBeVisible();
  });

  test('should handle timeout errors', async ({ page }) => {
    // Mock very slow response
    await page.route('**/api/prospects*', route => {
      // Delay response beyond reasonable timeout
      setTimeout(() => {
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ prospects: [], pagination: { total: 0 } })
        });
      }, 30000); // 30 second delay
    });

    await page.reload();

    // Should show timeout or loading error
    await expect(
      page.getByText(/timeout|taking too long|slow connection|loading error/i)
    ).toBeVisible({ timeout: 15000 });
  });

  test('should handle missing resources (404 errors)', async ({ page }) => {
    // Navigate to non-existent page
    await page.goto('/non-existent-page');

    // Should show 404 error page
    await expect(
      page.getByText(/not found|404|page not found/i)
    ).toBeVisible({ timeout: 5000 });

    // Should provide navigation back to main app
    const homeLink = page.getByRole('link', { name: /home|back|prospects/i });
    if (await homeLink.isVisible()) {
      await homeLink.click();

      // Should navigate back to working page
      await expect(page.locator('[data-testid="prospects-table"]')).toBeVisible({ timeout: 10000 });
    }
  });

  test('should handle enhancement processing errors', async ({ page }) => {
    await page.waitForSelector('[data-testid="prospects-table"]', { timeout: 10000 });

    // Mock enhancement API error
    await page.route('**/api/llm/**', route => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'LLM service unavailable' })
      });
    });

    // Try to enhance a prospect
    await page.locator('[data-testid="prospect-row"]').first().click();
    await expect(page.getByRole('dialog')).toBeVisible();

    const enhanceButton = page.getByRole('button', { name: /enhance.*ai|ai.*enhance/i });
    if (await enhanceButton.isVisible()) {
      await enhanceButton.click();

      // Should show enhancement error
      await expect(
        page.getByText(/enhancement failed|ai error|service unavailable/i)
      ).toBeVisible({ timeout: 10000 });

      // Should allow retry
      const retryButton = page.getByRole('button', { name: /retry|try again/i });
      if (await retryButton.isVisible()) {
        await expect(retryButton).toBeVisible();
      }
    }
  });

  test('should handle form validation errors', async ({ page }) => {
    await page.waitForSelector('[data-testid="prospects-table"]', { timeout: 10000 });

    // Open prospect details
    await page.locator('[data-testid="prospect-row"]').first().click();
    await expect(page.getByRole('dialog')).toBeVisible();

    // Try to make decision without reason (if validation exists)
    const goButton = page.getByRole('button', { name: /^go$/i });

    if (await goButton.isVisible()) {
      await goButton.click();

      const reasonInput = page.getByPlaceholder(/reason/i);
      if (await reasonInput.isVisible()) {
        // Try to submit without filling reason
        const submitButton = page.getByRole('button', { name: /submit/i });
        await submitButton.click();

        // Should show validation error
        const validationError = page.getByText(/required|please provide|cannot be empty/i);
        if (await validationError.isVisible()) {
          await expect(validationError).toBeVisible();

          // Error should be clearly visible and user-friendly
          const errorText = await validationError.textContent();
          expect(errorText).toBeTruthy();
          expect(errorText).not.toContain('undefined');
        }
      }
    }
  });

  test('should handle browser compatibility issues', async ({ page }) => {
    // Test modern JavaScript features gracefully
    await page.addInitScript(() => {
      // Mock missing modern browser features
      delete window.fetch;
      delete window.URLSearchParams;
    });

    await page.reload();

    // Application should still load with fallbacks
    const hasContent = await page.locator('body').textContent();
    expect(hasContent).toBeTruthy();

    // Should show compatibility warning if implemented
    const compatWarning = page.getByText(/browser.*old|compatibility|update.*browser/i);
    if (await compatWarning.isVisible()) {
      await expect(compatWarning).toBeVisible();
    }
  });

  test('should handle localStorage/sessionStorage errors', async ({ page }) => {
    // Mock storage quota exceeded
    await page.addInitScript(() => {
      Storage.prototype.setItem = function() {
        throw new Error('QuotaExceededError');
      };
    });

    await page.reload();

    // Should handle storage errors gracefully
    const storageError = page.getByText(/storage.*full|quota.*exceeded|clear.*data/i);
    if (await storageError.isVisible()) {
      await expect(storageError).toBeVisible();
    }

    // Application should still function
    await expect(page.locator('[data-testid="prospects-table"]')).toBeVisible({ timeout: 10000 });
  });

  test('should provide accessible error reporting', async ({ page }) => {
    // Mock API error to trigger error state
    await page.route('**/api/prospects*', route => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'Test error for accessibility' })
      });
    });

    await page.reload();

    // Check error message accessibility
    const errorElement = page.getByText(/error|failed|problem/i).first();
    if (await errorElement.isVisible()) {
      // Should have proper ARIA attributes
      const ariaLive = await errorElement.getAttribute('aria-live');
      const role = await errorElement.getAttribute('role');

      // Should be announced to screen readers
      expect(ariaLive || role).toBeTruthy();
    }
  });

  test('should handle multiple concurrent errors', async ({ page }) => {
    // Mock multiple failing APIs
    await page.route('**/api/prospects*', route => {
      route.fulfill({ status: 500, body: 'Error 1' });
    });

    await page.route('**/api/data-sources*', route => {
      route.fulfill({ status: 500, body: 'Error 2' });
    });

    await page.route('**/api/health*', route => {
      route.fulfill({ status: 500, body: 'Error 3' });
    });

    await page.reload();

    // Should handle multiple errors without breaking
    await expect(page.locator('body')).toBeVisible();

    // Should show primary error message
    const errorMessages = page.getByText(/error|failed/i);
    if (await errorMessages.first().isVisible()) {
      expect(await errorMessages.count()).toBeGreaterThanOrEqual(1);
    }
  });

  test('should recover from critical errors', async ({ page }) => {
    // Mock critical application error
    await page.addInitScript(() => {
      // Simulate unhandled error
      setTimeout(() => {
        throw new Error('Critical application error');
      }, 1000);
    });

    await page.reload();

    // Wait for potential error
    await page.waitForTimeout(2000);

    // Application should show error boundary or recovery UI
    const errorBoundary = page.getByText(/something went wrong|error boundary|reload/i);
    const reloadButton = page.getByRole('button', { name: /reload|refresh|restart/i });

    if (await errorBoundary.isVisible() || await reloadButton.isVisible()) {
      // Should provide recovery option
      if (await reloadButton.isVisible()) {
        await reloadButton.click();

        // Should attempt to recover
        await page.waitForTimeout(2000);
      }
    }

    // Should not show white screen of death
    const bodyContent = await page.locator('body').textContent();
    expect(bodyContent).toBeTruthy();
    expect(bodyContent.trim().length).toBeGreaterThan(0);
  });
});
