import { chromium, FullConfig } from '@playwright/test';

async function globalSetup(_config: FullConfig) {
  // Set up test database and seed data
  console.log('Setting up E2E test environment...');

  // You could add database seeding here
  // For example, create test users, prospects, etc.

  const browser = await chromium.launch();
  const page = await browser.newPage();

  try {
    // Wait for backend to be ready
    await page.goto('http://localhost:5001/api/health', {
      waitUntil: 'networkidle',
      timeout: 30000
    });

    // Wait for frontend to be ready
    await page.goto('http://localhost:3000', {
      waitUntil: 'networkidle',
      timeout: 30000
    });

    console.log('✅ E2E test environment is ready');
  } catch (error) {
    console.error('❌ Failed to set up E2E test environment:', error);
    throw error;
  }

  await browser.close();
}

export default globalSetup;
