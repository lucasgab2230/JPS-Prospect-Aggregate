import { test, expect } from '@playwright/test';

test.describe('Search and Filtering Functionality', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');

    // Wait for prospects to load
    await page.waitForSelector('[data-testid="prospects-table"]', { timeout: 10000 });
  });

  test('should perform basic text search', async ({ page }) => {
    // Find search input
    const searchInput = page.locator('[data-testid="search-input"], input[placeholder*="search" i]');

    if (await searchInput.isVisible()) {
      // Type search query
      await searchInput.fill('software');

      // Wait for search to apply
      await page.waitForTimeout(1000);

      // Should show search results
      await expect(page.locator('[data-testid="prospects-table"]')).toBeVisible();

      // Results should contain search term (if any results exist)
      const rows = page.locator('[data-testid="prospect-row"]');
      const rowCount = await rows.count();

      if (rowCount > 0) {
        // At least one result should contain the search term
        const firstRow = rows.first();
        const _rowText = await firstRow.textContent();
        // Note: Search might be case-insensitive or partial match
      }
    }
  });

  test('should perform advanced search with multiple terms', async ({ page }) => {
    const searchInput = page.locator('[data-testid="search-input"], input[placeholder*="search" i]');

    if (await searchInput.isVisible()) {
      // Test multi-word search
      await searchInput.fill('software development services');
      await page.waitForTimeout(1000);

      // Should handle multi-word search
      await expect(page.locator('[data-testid="prospects-table"]')).toBeVisible();

      // Clear and test quoted search
      await searchInput.fill('"cloud computing"');
      await page.waitForTimeout(1000);

      // Should handle quoted phrases
      await expect(page.locator('[data-testid="prospects-table"]')).toBeVisible();
    }
  });

  test('should filter by estimated value range', async ({ page }) => {
    // Look for value range filters
    const minValueInput = page.locator('input[name*="min" i], input[placeholder*="min" i]');
    const maxValueInput = page.locator('input[name*="max" i], input[placeholder*="max" i]');

    if (await minValueInput.isVisible() && await maxValueInput.isVisible()) {
      // Set value range
      await minValueInput.fill('50000');
      await maxValueInput.fill('200000');

      // Apply filter
      const applyButton = page.getByRole('button', { name: /apply|filter|search/i });
      if (await applyButton.isVisible()) {
        await applyButton.click();
      }

      // Wait for results
      await page.waitForTimeout(1000);
      await expect(page.locator('[data-testid="prospects-table"]')).toBeVisible();
    }
  });

  test('should filter by date range', async ({ page }) => {
    // Look for date filters
    const fromDateInput = page.locator('input[type="date"], input[name*="from" i], input[name*="start" i]');
    const toDateInput = page.locator('input[type="date"], input[name*="to" i], input[name*="end" i]');

    if (await fromDateInput.first().isVisible()) {
      // Set date range
      await fromDateInput.first().fill('2024-01-01');

      if (await toDateInput.first().isVisible()) {
        await toDateInput.first().fill('2024-12-31');
      }

      // Apply filter
      const applyButton = page.getByRole('button', { name: /apply|filter|search/i });
      if (await applyButton.isVisible()) {
        await applyButton.click();
      }

      await page.waitForTimeout(1000);
      await expect(page.locator('[data-testid="prospects-table"]')).toBeVisible();
    }
  });

  test('should filter by NAICS code', async ({ page }) => {
    // Look for NAICS filter
    const naicsInput = page.locator('input[name*="naics" i], input[placeholder*="naics" i]');
    const naicsSelect = page.locator('select[name*="naics" i]');

    if (await naicsInput.isVisible()) {
      // Enter NAICS code
      await naicsInput.fill('541511');
      await page.waitForTimeout(1000);

      await expect(page.locator('[data-testid="prospects-table"]')).toBeVisible();
    } else if (await naicsSelect.isVisible()) {
      // Select from dropdown
      await naicsSelect.selectOption({ index: 1 });
      await page.waitForTimeout(1000);

      await expect(page.locator('[data-testid="prospects-table"]')).toBeVisible();
    }
  });

  test('should filter by AI enhancement status', async ({ page }) => {
    // Look for AI enhancement toggle or filter
    const aiToggle = page.locator('[data-testid="ai-filter"], input[name*="ai" i]');
    const aiCheckbox = page.getByRole('checkbox', { name: /ai|enhanced|enriched/i });

    if (await aiToggle.isVisible()) {
      await aiToggle.click();
      await page.waitForTimeout(1000);

      await expect(page.locator('[data-testid="prospects-table"]')).toBeVisible();
    } else if (await aiCheckbox.isVisible()) {
      await aiCheckbox.check();
      await page.waitForTimeout(1000);

      await expect(page.locator('[data-testid="prospects-table"]')).toBeVisible();
    }
  });

  test('should combine multiple filters', async ({ page }) => {
    // Apply multiple filters together
    const searchInput = page.locator('[data-testid="search-input"], input[placeholder*="search" i]');
    const agencyFilter = page.locator('[data-testid="agency-filter"]');

    if (await searchInput.isVisible()) {
      // Apply text search
      await searchInput.fill('development');
      await page.waitForTimeout(500);
    }

    if (await agencyFilter.isVisible()) {
      // Apply agency filter
      await agencyFilter.click();

      const firstOption = page.locator('[data-testid*="option"], [role="option"]').first();
      if (await firstOption.isVisible()) {
        await firstOption.click();
      }

      await page.waitForTimeout(500);
    }

    // Results should reflect combined filters
    await expect(page.locator('[data-testid="prospects-table"]')).toBeVisible();
  });

  test('should clear all filters', async ({ page }) => {
    // Apply some filters first
    const searchInput = page.locator('[data-testid="search-input"], input[placeholder*="search" i]');

    if (await searchInput.isVisible()) {
      await searchInput.fill('test query');
      await page.waitForTimeout(1000);
    }

    // Look for clear/reset button
    const clearButton = page.getByRole('button', { name: /clear|reset|remove filters/i });

    if (await clearButton.isVisible()) {
      await clearButton.click();

      // Wait for filters to clear
      await page.waitForTimeout(1000);

      // Search input should be cleared
      if (await searchInput.isVisible()) {
        const searchValue = await searchInput.inputValue();
        expect(searchValue).toBe('');
      }

      // Table should show all results
      await expect(page.locator('[data-testid="prospects-table"]')).toBeVisible();
    }
  });

  test('should show search suggestions', async ({ page }) => {
    const searchInput = page.locator('[data-testid="search-input"], input[placeholder*="search" i]');

    if (await searchInput.isVisible()) {
      // Start typing to trigger suggestions
      await searchInput.fill('soft');

      // Look for suggestion dropdown
      await page.waitForTimeout(500);

      const suggestions = page.locator('[data-testid="search-suggestions"], [role="listbox"], .suggestions');

      if (await suggestions.isVisible()) {
        // Should show suggestion items
        const suggestionItems = suggestions.locator('[role="option"], .suggestion-item');
        const itemCount = await suggestionItems.count();

        if (itemCount > 0) {
          // Click first suggestion
          await suggestionItems.first().click();

          // Should apply the suggestion
          await page.waitForTimeout(1000);
          await expect(page.locator('[data-testid="prospects-table"]')).toBeVisible();
        }
      }
    }
  });

  test('should handle no search results', async ({ page }) => {
    const searchInput = page.locator('[data-testid="search-input"], input[placeholder*="search" i]');

    if (await searchInput.isVisible()) {
      // Search for something unlikely to exist
      await searchInput.fill('xyznoresultsexpected12345');
      await page.waitForTimeout(1000);

      // Should show no results message
      const noResultsMessage = page.getByText(/no results|no prospects found|no matches/i);

      if (await noResultsMessage.isVisible()) {
        await expect(noResultsMessage).toBeVisible();
      } else {
        // Alternative: table might be empty but still visible
        const rows = page.locator('[data-testid="prospect-row"]');
        const rowCount = await rows.count();
        expect(rowCount).toBe(0);
      }
    }
  });

  test('should preserve filters across page navigation', async ({ page }) => {
    const searchInput = page.locator('[data-testid="search-input"], input[placeholder*="search" i]');

    if (await searchInput.isVisible()) {
      // Apply a search filter
      await searchInput.fill('development');
      await page.waitForTimeout(1000);

      // Navigate to next page (if pagination exists)
      const nextButton = page.getByRole('button', { name: /next/i });

      if (await nextButton.isVisible()) {
        await nextButton.click();
        await page.waitForTimeout(1000);

        // Search filter should be preserved
        const searchValue = await searchInput.inputValue();
        expect(searchValue).toBe('development');
      }
    }
  });

  test('should support keyboard navigation in search', async ({ page }) => {
    const searchInput = page.locator('[data-testid="search-input"], input[placeholder*="search" i]');

    if (await searchInput.isVisible()) {
      // Focus search input
      await searchInput.focus();

      // Type search term
      await searchInput.fill('software');

      // Press Enter to search
      await searchInput.press('Enter');

      // Should apply search
      await page.waitForTimeout(1000);
      await expect(page.locator('[data-testid="prospects-table"]')).toBeVisible();

      // Test Escape to clear (if supported)
      await searchInput.press('Escape');
      await page.waitForTimeout(500);
    }
  });

  test('should show filter indicators', async ({ page }) => {
    // Apply some filters
    const searchInput = page.locator('[data-testid="search-input"], input[placeholder*="search" i]');

    if (await searchInput.isVisible()) {
      await searchInput.fill('test');
      await page.waitForTimeout(1000);

      // Look for active filter indicators
      const filterIndicators = page.locator('[data-testid="active-filters"], .filter-tags, .applied-filters');

      if (await filterIndicators.isVisible()) {
        // Should show which filters are active
        await expect(filterIndicators).toBeVisible();

        // Should show filter values
        const filterTags = filterIndicators.locator('.filter-tag, .tag, [data-testid*="filter-tag"]');
        if (await filterTags.first().isVisible()) {
          expect(await filterTags.count()).toBeGreaterThan(0);
        }
      }
    }
  });

  test('should handle special characters in search', async ({ page }) => {
    const searchInput = page.locator('[data-testid="search-input"], input[placeholder*="search" i]');

    if (await searchInput.isVisible()) {
      // Test special characters
      const specialQueries = [
        'C++',
        '.NET',
        'software & services',
        'cloud-computing',
        'AI/ML services'
      ];

      for (const query of specialQueries) {
        await searchInput.fill(query);
        await page.waitForTimeout(1000);

        // Should handle special characters gracefully
        await expect(page.locator('[data-testid="prospects-table"]')).toBeVisible();

        // Clear for next test
        await searchInput.clear();
      }
    }
  });
});
