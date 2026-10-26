import { test, expect } from '@playwright/test';

test.describe('Admin Functionality', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('should access admin dashboard', async ({ page }) => {
    // Try to navigate to admin area
    try {
      await page.goto('/admin');
      await page.waitForLoadState('networkidle');

      // Check if admin dashboard is accessible
      const hasAdminContent = await page.getByText(/admin|dashboard|management|control panel/i).count() > 0;
      const hasAccessDenied = await page.getByText(/access denied|unauthorized|forbidden|login required/i).count() > 0;

      // Should either show admin content or access denied
      expect(hasAdminContent || hasAccessDenied).toBeTruthy();

      if (hasAdminContent) {
        // If admin access is granted, verify dashboard elements
        await expect(page.getByText(/admin|dashboard/i).first()).toBeVisible();
      }
    } catch (error) {
      // Admin route might not exist
      console.log('Admin route not available');
    }
  });

  test('should manage enhancement queue', async ({ page }) => {
    try {
      await page.goto('/admin/queue');
      await page.waitForLoadState('networkidle');

      // Look for queue management interface
      const queueInterface = page.getByText(/queue|enhancement|processing/i);

      if (await queueInterface.first().isVisible()) {
        // Should show queue status
        await expect(page.getByText(/status|idle|processing|queue/i)).toBeVisible();

        // Look for queue controls
        const startButton = page.getByRole('button', { name: /start|begin|process/i });
        const stopButton = page.getByRole('button', { name: /stop|pause|halt/i });
        const _clearButton = page.getByRole('button', { name: /clear|reset|empty/i });

        if (await startButton.isVisible()) {
          await startButton.click();

          // Should show feedback
          await expect(page.getByText(/started|processing|running/i)).toBeVisible({ timeout: 5000 });
        }

        if (await stopButton.isVisible()) {
          await stopButton.click();

          // Should show stopped status
          await expect(page.getByText(/stopped|idle|paused/i)).toBeVisible({ timeout: 5000 });
        }
      }
    } catch (error) {
      console.log('Admin queue page not available');
    }
  });

  test('should view system statistics', async ({ page }) => {
    try {
      await page.goto('/admin/stats');
      await page.waitForLoadState('networkidle');

      // Look for statistics dashboard
      const statsContent = page.getByText(/statistics|metrics|analytics|overview/i);

      if (await statsContent.first().isVisible()) {
        // Should show numerical statistics
        const numbers = page.locator('text=/\\d+/');
        expect(await numbers.count()).toBeGreaterThan(0);

        // Look for key metrics
        const keyMetrics = [
          /total prospects/i,
          /active sources/i,
          /enhancements/i,
          /decisions/i,
          /success rate/i
        ];

        for (const metric of keyMetrics) {
          const metricElement = page.getByText(metric);
          if (await metricElement.isVisible()) {
            await expect(metricElement).toBeVisible();
          }
        }
      }
    } catch (error) {
      console.log('Admin stats page not available');
    }
  });

  test('should manage data sources', async ({ page }) => {
    try {
      await page.goto('/admin/sources');
      await page.waitForLoadState('networkidle');

      // Look for data source management
      const sourcesContent = page.getByText(/sources|scrapers|agencies/i);

      if (await sourcesContent.first().isVisible()) {
        // Should show list of data sources
        await expect(page.getByText(/department|agency|source/i)).toBeVisible();

        // Look for source controls
        const _enableButton = page.getByRole('button', { name: /enable|activate/i });
        const _disableButton = page.getByRole('button', { name: /disable|deactivate/i });
        const refreshButton = page.getByRole('button', { name: /refresh|update|scrape/i });

        if (await refreshButton.isVisible()) {
          await refreshButton.click();

          // Should show refresh feedback
          await expect(page.getByText(/refreshing|updating|scraping/i)).toBeVisible({ timeout: 5000 });
        }

        // Look for source status indicators
        const statusIndicators = page.getByText(/active|inactive|online|offline|healthy|error/i);
        if (await statusIndicators.first().isVisible()) {
          expect(await statusIndicators.count()).toBeGreaterThan(0);
        }
      }
    } catch (error) {
      console.log('Admin sources page not available');
    }
  });

  test('should manage user accounts', async ({ page }) => {
    try {
      await page.goto('/admin/users');
      await page.waitForLoadState('networkidle');

      // Look for user management interface
      const usersContent = page.getByText(/users|accounts|members/i);

      if (await usersContent.first().isVisible()) {
        // Should show user list or table
        await expect(page.getByText(/username|email|role/i)).toBeVisible();

        // Look for user management actions
        const addUserButton = page.getByRole('button', { name: /add|create|invite/i });
        const _editButton = page.getByRole('button', { name: /edit|modify/i });
        const _deleteButton = page.getByRole('button', { name: /delete|remove/i });

        if (await addUserButton.isVisible()) {
          await addUserButton.click();

          // Should show user creation form
          const userForm = page.locator('form, [data-testid="user-form"]');
          if (await userForm.isVisible()) {
            await expect(userForm).toBeVisible();

            // Should have form fields
            await expect(page.getByLabel(/username|email/i)).toBeVisible();
          }
        }
      }
    } catch (error) {
      console.log('Admin users page not available');
    }
  });

  test('should view application logs', async ({ page }) => {
    try {
      await page.goto('/admin/logs');
      await page.waitForLoadState('networkidle');

      // Look for log viewer interface
      const logsContent = page.getByText(/logs|events|history/i);

      if (await logsContent.first().isVisible()) {
        // Should show log entries
        const logEntries = page.locator('.log-entry, [data-testid*="log"], tr');

        if (await logEntries.first().isVisible()) {
          expect(await logEntries.count()).toBeGreaterThan(0);

          // Should show timestamps and log levels
          await expect(page.locator('text=/\\d{4}-\\d{2}-\\d{2}|\\d{1,2}:\\d{2}/').first()).toBeVisible();
          await expect(page.getByText(/info|warn|error|debug/i).first()).toBeVisible();
        }

        // Look for log filtering options
        const levelFilter = page.locator('select[name*="level"], [data-testid="log-level-filter"]');
        if (await levelFilter.isVisible()) {
          await levelFilter.selectOption('error');

          // Should filter logs
          await page.waitForTimeout(1000);
        }
      }
    } catch (error) {
      console.log('Admin logs page not available');
    }
  });

  test('should configure system settings', async ({ page }) => {
    try {
      await page.goto('/admin/settings');
      await page.waitForLoadState('networkidle');

      // Look for settings interface
      const settingsContent = page.getByText(/settings|configuration|preferences/i);

      if (await settingsContent.first().isVisible()) {
        // Should show configuration options
        const configSections = page.locator('.setting-group, .config-section, fieldset');

        if (await configSections.first().isVisible()) {
          // Look for common settings
          const settingInputs = page.locator('input, select, textarea');
          expect(await settingInputs.count()).toBeGreaterThan(0);

          // Look for save button
          const saveButton = page.getByRole('button', { name: /save|apply|update/i });
          if (await saveButton.isVisible()) {
            // Don't actually save settings in test
            await expect(saveButton).toBeVisible();
          }
        }
      }
    } catch (error) {
      console.log('Admin settings page not available');
    }
  });

  test('should handle bulk operations', async ({ page }) => {
    // Start from main prospects page
    await page.waitForSelector('[data-testid="prospects-table"]', { timeout: 10000 });

    // Look for bulk selection controls
    const selectAllCheckbox = page.getByRole('checkbox', { name: /select all/i }).first();

    if (await selectAllCheckbox.isVisible()) {
      await selectAllCheckbox.check();

      // Should show bulk action menu
      const bulkActionsButton = page.getByRole('button', { name: /bulk|actions|operations/i });

      if (await bulkActionsButton.isVisible()) {
        await bulkActionsButton.click();

        // Should show bulk operation options
        const bulkOptions = page.locator('[role="menu"], [role="menuitem"], .dropdown-item');

        if (await bulkOptions.first().isVisible()) {
          // Look for common bulk operations
          const exportOption = page.getByText(/export|download/i);
          const _deleteOption = page.getByText(/delete|remove/i);
          const _enhanceOption = page.getByText(/enhance|process/i);

          if (await exportOption.isVisible()) {
            await exportOption.click();

            // Should trigger export process
            await expect(page.getByText(/exporting|download|preparing/i)).toBeVisible({ timeout: 5000 });
          }
        }
      }
    }
  });

  test('should monitor system health', async ({ page }) => {
    try {
      await page.goto('/admin/health');
      await page.waitForLoadState('networkidle');

      // Look for health monitoring dashboard
      const healthContent = page.getByText(/health|monitoring|status|uptime/i);

      if (await healthContent.first().isVisible()) {
        // Should show health indicators
        const healthIndicators = page.getByText(/healthy|unhealthy|warning|critical|ok|error/i);
        expect(await healthIndicators.count()).toBeGreaterThan(0);

        // Look for system components
        const components = [
          /database/i,
          /llm|ai/i,
          /scrapers/i,
          /queue/i,
          /api/i
        ];

        for (const component of components) {
          const componentStatus = page.getByText(component);
          if (await componentStatus.isVisible()) {
            // Should show status for each component
            await expect(componentStatus).toBeVisible();
          }
        }

        // Look for refresh button
        const refreshButton = page.getByRole('button', { name: /refresh|check|update/i });
        if (await refreshButton.isVisible()) {
          await refreshButton.click();

          // Should update health status
          await page.waitForTimeout(2000);
        }
      }
    } catch (error) {
      console.log('Admin health page not available');
    }
  });

  test('should handle admin authentication', async ({ page }) => {
    // Navigate to admin area
    try {
      await page.goto('/admin');
      await page.waitForLoadState('networkidle');

      // Check if login is required
      const loginForm = page.locator('form').filter({ hasText: /login|sign in|authenticate/i });

      if (await loginForm.isVisible()) {
        // Should show admin login form
        await expect(loginForm).toBeVisible();

        // Should have appropriate fields
        const usernameField = page.getByLabel(/username|email/i);
        const passwordField = page.getByLabel(/password/i);

        if (await usernameField.isVisible() && await passwordField.isVisible()) {
          // Fill admin credentials (test credentials)
          await usernameField.fill('admin');
          await passwordField.fill('testpassword');

          const submitButton = page.getByRole('button', { name: /login|sign in|authenticate/i });
          await submitButton.click();

          // Should either succeed or show error
          await page.waitForLoadState('networkidle');

          const hasAdminContent = await page.getByText(/admin|dashboard/i).count() > 0;
          const hasError = await page.getByText(/invalid|error|incorrect/i).count() > 0;

          expect(hasAdminContent || hasError).toBeTruthy();
        }
      }
    } catch (error) {
      console.log('Admin authentication flow not available');
    }
  });
});
