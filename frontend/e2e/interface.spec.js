import { test, expect } from '@playwright/test';

test('chat and knowledge pages are usable without horizontal overflow', async ({ page }, info) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Farming assistant', exact: true })).toBeVisible();
  await expect(page.locator('.greeting')).toContainText('नमस्ते');
  await expect(page.getByRole('heading', { name: /What's growing/ })).toBeVisible();
  await expect(page.locator('.panel-top')).toContainText('नेपाली');
  expect(await page.locator('.field-photo img').evaluate(image => image.complete && image.naturalWidth > 0)).toBe(true);
  await page.getByRole('button', { name: /Organic ginger cultivation/ }).click();
  await expect(page.getByLabel('Your farming question')).toHaveValue('How do I grow organic ginger in Sikkim?');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: `../.runtime/chat-${info.project.name}.png`, fullPage: true });
  await page.getByRole('navigation').getByRole('link', { name: 'Knowledge Base', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Knowledge Base', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Upload & index' })).toBeDisabled();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: `../.runtime/knowledge-${info.project.name}.png`, fullPage: true });
  expect(errors).toEqual([]);
});
