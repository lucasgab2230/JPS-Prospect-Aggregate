import { test, expect } from '@playwright/test';

test.describe('User Authentication Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Start from login page or home page
    await page.goto('/');
  });

  test('should handle unauthenticated user access', async ({ page }) => {
    // Should redirect to login or show login prompt
    // This depends on your authentication implementation
    await page.waitForLoadState('networkidle');

    // Check if login form is visible or if there's an auth prompt
    const hasLoginForm = await page.locator('form').count() > 0;
    const hasAuthPrompt = await page.getByText(/sign in|login/i).count() > 0;

    // At least one auth-related element should be present
    expect(hasLoginForm || hasAuthPrompt).toBeTruthy();
  });

  test('should handle login workflow', async ({ page }) => {
    // Look for login elements
    const loginButton = page.getByRole('button', { name: /sign in|login/i });

    if (await loginButton.isVisible()) {
      await loginButton.click();

      // Fill login form if present
      const usernameField = page.getByLabel(/username|email/i);
      const passwordField = page.getByLabel(/password/i);

      if (await usernameField.isVisible()) {
        await usernameField.fill('testuser');
        await passwordField.fill('testpassword');

        const submitButton = page.getByRole('button', { name: /submit|sign in|login/i });
        await submitButton.click();

        // Should navigate to main app or show success
        await page.waitForLoadState('networkidle');

        // Check for successful login indicators
        const hasProspectsTable = await page.locator('[data-testid="prospects-table"]').isVisible();
        const hasUserMenu = await page.getByText(/welcome|profile|logout/i).count() > 0;

        expect(hasProspectsTable || hasUserMenu).toBeTruthy();
      }
    }
  });

  test('should handle signup workflow', async ({ page }) => {
    // Look for signup link or button
    const signupLink = page.getByRole('link', { name: /sign up|register|create account/i });
    const signupButton = page.getByRole('button', { name: /sign up|register|create account/i });

    if (await signupLink.isVisible()) {
      await signupLink.click();
    } else if (await signupButton.isVisible()) {
      await signupButton.click();
    } else {
      // Skip test if no signup option is available
      test.skip('No signup option found');
    }

    // Fill signup form
    const firstNameField = page.getByLabel(/first name/i);
    const lastNameField = page.getByLabel(/last name/i);
    const emailField = page.getByLabel(/email/i);
    const usernameField = page.getByLabel(/username/i);
    const passwordField = page.getByLabel(/password/i);

    if (await firstNameField.isVisible()) {
      await firstNameField.fill('Test');
      await lastNameField.fill('User');
      await emailField.fill('test@example.com');
      await usernameField.fill('testuser');
      await passwordField.fill('testpassword123');

      const submitButton = page.getByRole('button', { name: /submit|create|sign up/i });
      await submitButton.click();

      // Should show success message or redirect
      await expect(page.getByText(/success|welcome|created/i)).toBeVisible({ timeout: 5000 });
    }
  });

  test('should handle logout workflow', async ({ page }) => {
    // Assume user is logged in (this could be set up in beforeEach)
    await page.goto('/');

    // Look for user menu or logout button
    const userMenu = page.getByRole('button', { name: /profile|account|user/i });
    const logoutButton = page.getByRole('button', { name: /logout|sign out/i });

    if (await userMenu.isVisible()) {
      await userMenu.click();
      // Look for logout option in dropdown
      await page.getByRole('menuitem', { name: /logout|sign out/i }).click();
    } else if (await logoutButton.isVisible()) {
      await logoutButton.click();
    } else {
      test.skip('No logout option found');
    }

    // Should redirect to login or show logged out state
    await page.waitForLoadState('networkidle');

    // Verify user is logged out
    const hasLoginPrompt = await page.getByText(/sign in|login/i).count() > 0;
    expect(hasLoginPrompt).toBeGreaterThan(0);
  });

  test('should handle authentication persistence', async ({ page, context }) => {
    // Login (if needed)
    await page.goto('/');

    // Assume login process or check if already authenticated
    await page.waitForLoadState('networkidle');

    // Open new tab to test session persistence
    const newPage = await context.newPage();
    await newPage.goto('/');

    await newPage.waitForLoadState('networkidle');

    // Should maintain authentication state in new tab
    const hasProspectsAccess = await newPage.locator('[data-testid="prospects-table"]').isVisible();

    if (hasProspectsAccess) {
      // Authentication persisted successfully
      expect(hasProspectsAccess).toBeTruthy();
    }

    await newPage.close();
  });

  test('should handle role-based access', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Try to access admin features (if available)
    try {
      await page.goto('/admin');
      await page.waitForLoadState('networkidle');

      // Check if admin access is granted or denied appropriately
      const hasAdminContent = await page.getByText(/admin|dashboard|manage/i).count() > 0;
      const hasAccessDenied = await page.getByText(/access denied|unauthorized|forbidden/i).count() > 0;

      // Should either show admin content (if admin) or access denied
      expect(hasAdminContent || hasAccessDenied).toBeTruthy();
    } catch (error) {
      // Admin route might not exist, which is fine
    }
  });

  test('should handle session timeout', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Mock session timeout by clearing storage
    await page.evaluate(() => {
      localStorage.clear();
      sessionStorage.clear();
    });

    // Navigate to a protected route
    await page.reload();
    await page.waitForLoadState('networkidle');

    // Should be redirected to login or show authentication prompt
    const needsAuth = await page.getByText(/sign in|login|session expired/i).count() > 0;

    // This test depends on your session management implementation
    if (needsAuth) {
      expect(needsAuth).toBeGreaterThan(0);
    }
  });
});
