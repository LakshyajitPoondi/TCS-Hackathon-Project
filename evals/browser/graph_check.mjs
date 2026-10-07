import { chromium } from 'playwright-core';
const PW = process.argv[2];
const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 1000 } })).newPage();
page.on('pageerror', (e) => console.log('PAGE ERROR', e.message));
await page.goto('http://localhost:5173/login');
await page.getByLabel('Email').fill('engineer@demo.local');
await page.getByLabel('Password', { exact: true }).fill(PW);
await page.getByRole('button', { name: /open dashboard/i }).click();
await page.getByRole('heading', { name: /welcome/i }).waitFor();
for (const id of ['INC-001', 'INC-008']) {
  await page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: /^Incidents/ }).click();
  await page.getByRole('row', { name: new RegExp(id) }).click();
  await Promise.all([page.waitForResponse((r) => r.url().endsWith('/analyze')), page.getByRole('button', { name: /run rca analysis/i }).click()]);
  const graph = page.getByLabel('Cause-and-effect graph');
  await graph.locator('.react-flow__node').first().waitFor({ timeout: 30000 });
  const n = await graph.locator('.react-flow__node').count(), e = await graph.locator('.react-flow__edge').count();
  const labels = await graph.locator('.react-flow__edge-text').evaluateAll((els) => els.map((x) => x.textContent || ''));
  await graph.scrollIntoViewIfNeeded();
  await graph.locator('.react-flow__node').filter({ hasText: id === 'INC-001' ? 'Hypothesis' : 'Abstained' }).first().click();
  await page.waitForTimeout(400);
  const dimmed = await graph.locator('.opacity-25').count();
  const detail = await page.getByText(/Click a node|←|→/).count();
  await page.locator('section', { hasText: 'Cause-and-effect graph' }).first().screenshot({ path: `shots/graph-${id}.png` });
  console.log(id, { nodes: n, edges: e, weightLabels: labels.filter((l) => /^[+−]/.test(l)).length, dimmedAfterClick: dimmed, detailLines: detail });
}
await browser.close();
