import { test, expect } from '@playwright/test';

test('assistant formatting renders as HTML without overflowing the conversation', async ({ page }, info) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const answer = `## Large cardamom disease

* **Climate Change and Weather Patterns:** Rising temperatures and wet and dry spells [1].
* **Specific Pathogens:**
  * **Viral Diseases:** Chirkey and Foorkey [1].
  * **Fungal Diseases:** *Colletotrichum* causes blight [1].

Read the [source guide](https://example.org/cardamom).

| Disease | Type | Notes |
| --- | --- | --- |
| Chirkey | Viral | A source-backed description of symptoms and environmental conditions. |
| Blight | Fungal | Review the cited source for locally applicable guidance. |

> Check the source before acting.

Use \`compost\` according to source guidance [1].`;
  await page.route('**/api/health', route => route.fulfill({ json: { status: 'ready', llm_configured: true } }));
  await page.route('**/api/documents', route => route.fulfill({ json: { documents: [], document_count: 1, chunk_count: 1 } }));
  await page.route('**/api/chat', route => route.fulfill({ json: {
    answer, detected_language: 'en', evidence_status: 'supported',
    citations: [{ id: 1, title: 'Cardamom source', document_id: 'formatting-fixture', chunk_id: 'formatting-fixture' }],
  } }));
  await page.goto('/');
  await page.getByLabel('Your farming question').fill('Why does large cardamom get diseases?');
  await page.getByRole('button', { name: 'Send question' }).click();
  const message = page.locator('.message.assistant .message-text');
  await expect(message.getByRole('heading', { name: 'Large cardamom disease' })).toBeVisible();
  await expect(message.locator('strong').first()).toHaveText('Climate Change and Weather Patterns:');
  await expect(message.locator('em')).toHaveText('Colletotrichum');
  await expect(message.locator('ul ul li')).toHaveCount(2);
  await expect(message.getByRole('link', { name: 'source guide' })).toHaveAttribute('href', 'https://example.org/cardamom');
  await expect(message.getByRole('table')).toBeVisible();
  await expect(message.locator('code')).toHaveText('compost');
  await expect(page.getByRole('button', { name: /Cardamom source/ })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(await page.locator('.chat-window').evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true);
  await page.screenshot({ path: `../.runtime/message-formatting-${info.project.name}.png`, fullPage: true });
  expect(errors).toEqual([]);
});
