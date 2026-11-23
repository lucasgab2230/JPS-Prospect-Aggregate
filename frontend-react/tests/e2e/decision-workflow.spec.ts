import { test, expect } from '@playwright/test';

test.describe('Decision Workflow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');

    // Wait for prospects to load
    await page.waitForSelector('[data-testid="prospects-table"]', { timeout: 10000 });
  });

  test('should complete go decision workflow', async ({ page }) => {
    // Click on first prospect to open details
    await page.locator('[data-testid="prospect-row"]').first().click();

    // Wait for modal to open
    await expect(page.getByRole('dialog')).toBeVisible();

    // Look for decision section
    const goButton = page.getByRole('button', { name: /^go$/i });

    if (await goButton.isVisible()) {
      await goButton.click();

      // Should show reason input
      const reasonInput = page.getByPlaceholder(/reason for your decision/i);
      await expect(reasonInput).toBeVisible();

      // Fill in reason
      await reasonInput.fill('This opportunity aligns well with our capabilities and strategic goals. The estimated value is appropriate for our team size.');

      // Submit decision
      const submitButton = page.getByRole('button', { name: /submit decision/i });
      await submitButton.click();

      // Should show success message or confirmation
      await expect(page.getByText(/decision recorded|success/i)).toBeVisible({ timeout: 5000 });

      // Verify decision is displayed
      await expect(page.getByText(/go/i)).toBeVisible();
      await expect(page.getByText('This opportunity aligns well')).toBeVisible();
    }
  });

  test('should complete no-go decision workflow', async ({ page }) => {
    // Click on second prospect to open details
    const prospectRows = page.locator('[data-testid="prospect-row"]');
    if (await prospectRows.count() > 1) {
      await prospectRows.nth(1).click();
    } else {
      await prospectRows.first().click();
    }

    await expect(page.getByRole('dialog')).toBeVisible();

    const noGoButton = page.getByRole('button', { name: /no.?go/i });

    if (await noGoButton.isVisible()) {
      await noGoButton.click();

      const reasonInput = page.getByPlaceholder(/reason for your decision/i);
      await expect(reasonInput).toBeVisible();

      await reasonInput.fill('This project does not align with our current strategic focus and the timeline is too aggressive for our current capacity.');

      const submitButton = page.getByRole('button', { name: /submit decision/i });
      await submitButton.click();

      await expect(page.getByText(/decision recorded|success/i)).toBeVisible({ timeout: 5000 });

      // Verify no-go decision is displayed
      await expect(page.getByText(/no.?go/i)).toBeVisible();
    }
  });

  test('should handle decision validation', async ({ page }) => {
    await page.locator('[data-testid="prospect-row"]').first().click();
    await expect(page.getByRole('dialog')).toBeVisible();

    const goButton = page.getByRole('button', { name: /^go$/i });

    if (await goButton.isVisible()) {
      await goButton.click();

      const reasonInput = page.getByPlaceholder(/reason for your decision/i);
      await expect(reasonInput).toBeVisible();

      // Try to submit without reason
      const submitButton = page.getByRole('button', { name: /submit decision/i });
      await submitButton.click();

      // Should show validation error
      await expect(page.getByText(/reason is required|please provide a reason/i)).toBeVisible({ timeout: 3000 });

      // Fill in minimal reason and try again
      await reasonInput.fill('A');
      await submitButton.click();

      // Should show error for too short reason
      const hasLengthError = await page.getByText(/reason must be|too short|minimum/i).isVisible();

      if (hasLengthError) {
        // Fill in proper reason
        await reasonInput.fill('This is a valid reason for the decision.');
        await submitButton.click();

        // Should succeed now
        await expect(page.getByText(/decision recorded|success/i)).toBeVisible({ timeout: 5000 });
      }
    }
  });

  test('should allow decision updates', async ({ page }) => {
    await page.locator('[data-testid="prospect-row"]').first().click();
    await expect(page.getByRole('dialog')).toBeVisible();

    const goButton = page.getByRole('button', { name: /^go$/i });

    if (await goButton.isVisible()) {
      // Make initial go decision
      await goButton.click();

      const reasonInput = page.getByPlaceholder(/reason for your decision/i);
      await reasonInput.fill('Initial go decision.');

      const submitButton = page.getByRole('button', { name: /submit decision/i });
      await submitButton.click();

      await expect(page.getByText(/decision recorded/i)).toBeVisible({ timeout: 5000 });

      // Change to no-go decision
      const noGoButton = page.getByRole('button', { name: /no.?go/i });
      await noGoButton.click();

      // Should clear previous reason or show new input
      await reasonInput.fill('Changed my mind - this is now a no-go.');
      await submitButton.click();

      await expect(page.getByText(/decision recorded/i)).toBeVisible({ timeout: 5000 });

      // Should show updated decision
      await expect(page.getByText(/no.?go/i)).toBeVisible();
      await expect(page.getByText('Changed my mind')).toBeVisible();
    }
  });

  test('should display decision history', async ({ page }) => {
    await page.locator('[data-testid="prospect-row"]').first().click();
    await expect(page.getByRole('dialog')).toBeVisible();

    // Look for decision history section
    const historySection = page.getByText(/decision history|previous decisions/i);

    if (await historySection.isVisible()) {
      // Should show list of previous decisions
      const decisionItems = page.locator('[data-testid*="decision-item"], .decision-item');
      const itemCount = await decisionItems.count();

      if (itemCount > 0) {
        // Verify decision items contain expected information
        const firstDecision = decisionItems.first();

        // Should show decision type, date, and user
        await expect(firstDecision.getByText(/go|no.?go/i)).toBeVisible();
        await expect(firstDecision.getByText(/\d{1,2}\/\d{1,2}\/\d{4}|\d{4}-\d{2}-\d{2}/)).toBeVisible();
      }
    }
  });

  test('should handle decision deletion', async ({ page }) => {
    await page.locator('[data-testid="prospect-row"]').first().click();
    await expect(page.getByRole('dialog')).toBeVisible();

    // Make a decision first
    const goButton = page.getByRole('button', { name: /^go$/i });

    if (await goButton.isVisible()) {
      await goButton.click();

      const reasonInput = page.getByPlaceholder(/reason for your decision/i);
      await reasonInput.fill('Decision to be deleted.');

      const submitButton = page.getByRole('button', { name: /submit decision/i });
      await submitButton.click();

      await expect(page.getByText(/decision recorded/i)).toBeVisible({ timeout: 5000 });

      // Look for delete button
      const deleteButton = page.getByRole('button', { name: /delete|remove decision/i });

      if (await deleteButton.isVisible()) {
        await deleteButton.click();

        // Should show confirmation dialog
        await expect(page.getByText(/are you sure|confirm deletion/i)).toBeVisible();

        // Confirm deletion
        const confirmButton = page.getByRole('button', { name: /yes|confirm|delete/i });
        await confirmButton.click();

        // Should show success message
        await expect(page.getByText(/decision deleted|removed/i)).toBeVisible({ timeout: 5000 });

        // Decision should no longer be visible
        await expect(page.getByText('Decision to be deleted.')).not.toBeVisible();
      }
    }
  });

  test('should display decision statistics', async ({ page }) => {
    // Navigate to decisions or statistics page
    const decisionsLink = page.getByRole('link', { name: /decisions|my decisions/i });

    if (await decisionsLink.isVisible()) {
      await decisionsLink.click();
      await page.waitForLoadState('networkidle');

      // Should show decision statistics
      const statsSection = page.getByText(/statistics|summary|overview/i);

      if (await statsSection.isVisible()) {
        // Look for key metrics
        await expect(page.getByText(/total decisions/i)).toBeVisible();
        await expect(page.getByText(/go decisions/i)).toBeVisible();
        await expect(page.getByText(/no.?go decisions/i)).toBeVisible();

        // Should show numerical values
        await expect(page.locator('text=/\\d+/')).toBeVisible();
      }
    }
  });

  test('should handle bulk decisions', async ({ page }) => {
    // Look for bulk action controls
    const selectAllCheckbox = page.getByRole('checkbox', { name: /select all/i });

    if (await selectAllCheckbox.isVisible()) {
      await selectAllCheckbox.click();

      // Should show bulk action options
      const bulkActionButton = page.getByRole('button', { name: /bulk actions|actions/i });

      if (await bulkActionButton.isVisible()) {
        await bulkActionButton.click();

        // Look for bulk decision options
        const bulkGoOption = page.getByRole('menuitem', { name: /mark as go/i });
        const _bulkNoGoOption = page.getByRole('menuitem', { name: /mark as no.?go/i });

        if (await bulkGoOption.isVisible()) {
          await bulkGoOption.click();

          // Should show bulk reason input
          const bulkReasonInput = page.getByPlaceholder(/reason for bulk decision/i);

          if (await bulkReasonInput.isVisible()) {
            await bulkReasonInput.fill('Bulk go decision for selected prospects.');

            const confirmBulkButton = page.getByRole('button', { name: /apply to selected/i });
            await confirmBulkButton.click();

            // Should show success message
            await expect(page.getByText(/bulk decisions applied/i)).toBeVisible({ timeout: 10000 });
          }
        }
      }
    }
  });

  test('should export decisions', async ({ page }) => {
    // Navigate to decisions page
    const decisionsLink = page.getByRole('link', { name: /decisions|my decisions/i });

    if (await decisionsLink.isVisible()) {
      await decisionsLink.click();
      await page.waitForLoadState('networkidle');

      // Look for export button
      const exportButton = page.getByRole('button', { name: /export|download/i });

      if (await exportButton.isVisible()) {
        // Set up download listener
        const downloadPromise = page.waitForEvent('download');

        await exportButton.click();

        // Should trigger download
        const download = await downloadPromise;

        // Verify download
        expect(download.suggestedFilename()).toMatch(/decisions.*\.(csv|xlsx|json)/i);
      }
    }
  });

  test('should handle decision conflicts', async ({ page, context }) => {
    // Open same prospect in two tabs to simulate concurrent editing
    await page.locator('[data-testid="prospect-row"]').first().click();
    await expect(page.getByRole('dialog')).toBeVisible();

    // Open second tab
    const secondPage = await context.newPage();
    await secondPage.goto('/');
    await secondPage.waitForSelector('[data-testid="prospects-table"]', { timeout: 10000 });
    await secondPage.locator('[data-testid="prospect-row"]').first().click();
    await expect(secondPage.getByRole('dialog')).toBeVisible();

    // Make decision in first tab
    const goButton1 = page.getByRole('button', { name: /^go$/i });
    if (await goButton1.isVisible()) {
      await goButton1.click();
      const reasonInput1 = page.getByPlaceholder(/reason for your decision/i);
      await reasonInput1.fill('First tab decision.');
      const submitButton1 = page.getByRole('button', { name: /submit decision/i });
      await submitButton1.click();
      await expect(page.getByText(/decision recorded/i)).toBeVisible({ timeout: 5000 });
    }

    // Try to make conflicting decision in second tab
    const noGoButton2 = secondPage.getByRole('button', { name: /no.?go/i });
    if (await noGoButton2.isVisible()) {
      await noGoButton2.click();
      const reasonInput2 = secondPage.getByPlaceholder(/reason for your decision/i);
      await reasonInput2.fill('Second tab decision.');
      const submitButton2 = secondPage.getByRole('button', { name: /submit decision/i });
      await submitButton2.click();

      // Should either succeed (overriding) or show conflict warning
      const hasSuccess = await secondPage.getByText(/decision recorded/i).isVisible();
      const hasConflict = await secondPage.getByText(/conflict|already decided/i).isVisible();

      expect(hasSuccess || hasConflict).toBeTruthy();
    }

    await secondPage.close();
  });
});
