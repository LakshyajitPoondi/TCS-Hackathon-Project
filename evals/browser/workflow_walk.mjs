// Headless walk of the 8-step workflow (audit_report_v2.md section 5). No reloads used as workarounds,
// no hand-typed URLs except the app root. Usage: node walk.mjs <password>
import { chromium } from 'playwright-core';
import fs from 'node:fs';
import path from 'node:path';

const BASE = 'http://localhost:5173';
const PW = process.argv[2];
const OUT = path.resolve('shots');
fs.mkdirSync(OUT, { recursive: true });
const results = [];
const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true });

async function session(email) {
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 1000 }, acceptDownloads: true });
  const page = await ctx.newPage();
  page.on('pageerror', (e) => console.log('PAGE ERROR', e.message));
  await page.goto(BASE + '/login');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password', { exact: true }).fill(PW);
  await page.getByRole('button', { name: /open dashboard/i }).click();
  await page.getByRole('heading', { name: /welcome/i }).waitFor({ timeout: 20000 });
  return { ctx, page };
}

async function step(name, fn) {
  const started = Date.now();
  try { const note = await fn(); results.push({ step: name, passed: true, note: note || '', ms: Date.now() - started }); console.log('PASS', name, note || ''); }
  catch (e) { results.push({ step: name, passed: false, note: String(e.message).split('\n')[0], ms: Date.now() - started }); console.log('FAIL', name, e.message); }
}

const nav = (page, label) => page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: new RegExp('^' + label) }).click();
const csv = fs.readFileSync('C:/Users/laksh/Documents/TCS Tech Day/data/incidents/incident_001.csv');
let uploadedId = '';

// 1. Admin: machines, upload a scoped manual, resolve a conflict.
await step('1 admin: machines, scoped upload, conflict resolved', async () => {
  const { ctx, page } = await session('admin@demo.local');
  await nav(page, 'Machines');
  await page.getByRole('link', { name: 'LINE-A/IMM-02' }).waitFor();
  const cards = await page.locator('a[href^="/machines/LINE-"]').count();
  if (cards !== 9) throw new Error('expected 9 machines, got ' + cards);
  await page.getByRole('link', { name: 'LINE-A/IMM-02' }).click();
  await page.getByRole('heading', { name: 'Related incidents' }).waitFor();
  await nav(page, 'Documents');
  await page.getByText('Upload machine documentation').click();
  const form = page.locator('form').first();
  await form.getByLabel('Title').fill('IMM-03 cooling manual');
  await form.getByLabel('Scope').selectOption('machine');
  await form.getByLabel(/Targets/).selectOption(['LINE-A/IMM-03']);
  await form.locator('input[type=file]').setInputFiles({ name: 'LINE-A_IMM-03_manual.md', mimeType: 'text/markdown', buffer: Buffer.from('# Cooling\nLINE-A/IMM-03 cooling checks.\n1. Check coolant flow on LINE-A/IMM-03.\n') });
  await form.getByRole('button', { name: /upload document/i }).click();
  await page.getByText(/Uploaded .*IMM-03 cooling manual.* · active/).waitFor({ timeout: 30000 });
  await form.getByLabel('Title').fill('Conflicting manual');
  await form.getByLabel('Scope').selectOption('machine');
  await form.getByLabel(/Targets/).selectOption(['LINE-A/IMM-02']);
  await form.locator('input[type=file]').setInputFiles({ name: 'manual.md', mimeType: 'text/markdown', buffer: Buffer.from('# Manual\nLINE-C/IMM-01 cooling checks.\n') });
  await form.getByRole('button', { name: /upload document/i }).click();
  await page.getByText(/Explicit mapping disagrees/).first().waitFor({ timeout: 30000 });
  const badge = await page.getByRole('navigation', { name: 'Main' }).getByLabel(/pending/).first().textContent({ timeout: 15000 });
  await page.getByRole('link', { name: /review and confirm mapping/i }).click();
  await page.getByRole('button', { name: /confirm mapping and activate/i }).click();
  await page.getByText(/· active/).first().waitFor();
  await ctx.close();
  return 'pending badge showed ' + badge;
});

// 2. Engineer: upload CSV, find it in the list (no URL), run analysis.
await step('2 engineer: upload CSV, listed as Uploaded, analysis', async () => {
  const { ctx, page } = await session('engineer@demo.local');
  await nav(page, 'Upload data');
  await page.locator('#csv-input').setInputFiles({ name: 'line_a_copy.csv', mimeType: 'text/csv', buffer: csv });
  await page.getByRole('button', { name: /^upload$/i }).click();
  await page.waitForURL(/\/incidents\/UPL-/, { timeout: 30000 });
  uploadedId = page.url().split('/').pop();
  await nav(page, 'Incidents');
  const row = page.getByRole('row', { name: new RegExp(uploadedId) });
  await row.waitFor();
  if (!(await row.getByText('Uploaded').count())) throw new Error('no Uploaded label');
  if (!(await row.getByText('New').count())) throw new Error('status not New');
  await row.click();
  await page.getByRole('button', { name: /run rca analysis/i }).click();
  await page.getByRole('heading', { name: 'Ranked hypotheses' }).waitFor({ timeout: 90000 });
  await page.getByText('Analysed', { exact: true }).first().waitFor();
  await ctx.close();
  return uploadedId;
});

// 3. Engineer: results, edit + save draft (versions), reload survives, export MD + PDF.
await step('3 engineer: hypotheses, documents, trace, draft versions, export', async () => {
  const { ctx, page } = await session('engineer@demo.local');
  await nav(page, 'Incidents');
  await page.getByRole('row', { name: new RegExp(uploadedId) }).click();
  await page.getByRole('heading', { name: 'Documents accessed' }).waitFor({ timeout: 30000 });
  await page.getByText('Agent trace').click();
  const box = page.locator('#rca-draft');
  await box.fill((await box.inputValue()) + '\nEngineer note: chiller filter found clogged.');
  await page.getByRole('button', { name: 'Save version' }).click();
  await page.getByText('Saved as version 1.').waitFor();
  await box.fill((await box.inputValue()) + '\nSecond edit.');
  await page.getByLabel(/version note/i).fill('second pass');
  await page.getByRole('button', { name: 'Save version' }).click();
  await page.getByText('Saved as version 2.').waitFor();
  await page.reload();
  await page.locator('#rca-draft').waitFor({ timeout: 30000 });
  await page.waitForFunction(() => document.querySelector('#rca-draft')?.value.includes('Second edit.'), null, { timeout: 30000 });
  const versions = await page.getByText(/^Version \d+$/).count();
  if (versions < 2) throw new Error('version history shows ' + versions);
  await page.getByText('Draft saved', { exact: true }).first().waitFor();
  const [md] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: 'Markdown' }).click()]);
  const mdText = fs.readFileSync(await md.path(), 'utf8');
  if (!mdText.includes('Engineering validation is required')) throw new Error('notice missing from Markdown');
  const [pdf] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: 'PDF' }).click()]);
  const pdfBytes = fs.readFileSync(await pdf.path());
  if (pdfBytes.subarray(0, 4).toString() !== '%PDF') throw new Error('PDF invalid');
  await page.screenshot({ path: path.join(OUT, 'step3-draft.png'), fullPage: true });
  await ctx.close();
  return `${versions} versions, ${md.suggestedFilename()}, ${pdf.suggestedFilename()} (${pdfBytes.length} bytes)`;
});

// 4. Engineer: propose case; incident shows "Case proposed".
await step('4 engineer: propose case', async () => {
  const { ctx, page } = await session('engineer@demo.local');
  await nav(page, 'Incidents');
  await page.getByRole('row', { name: new RegExp(uploadedId) }).click();
  await page.getByRole('button', { name: /propose case/i }).click();
  const dialog = page.getByRole('dialog');
  await dialog.waitFor();
  await proposeInDialog(page, dialog);
  await dialog.getByText(/Case proposed/).first().waitFor({ timeout: 30000 });
  await dialog.getByRole('button', { name: /done/i }).click();
  await page.getByText('Case proposed', { exact: true }).first().waitFor();
  await ctx.close();
});

async function proposeInDialog(page, dialog) {
  // Stage 3 modal: category/subcause/fix. (Stage 4 adds a generated, editable summary step.)
  const generate = dialog.getByRole('button', { name: /generate draft|next/i });
  if (await generate.count()) { await generate.first().click(); await dialog.getByLabel(/summary/i).first().waitFor({ timeout: 60000 }); }
  await dialog.getByLabel(/confirmed category/i).selectOption('machine');
  await dialog.getByLabel(/subcause/i).selectOption('cooling');
  await dialog.getByLabel(/fix applied/i).fill('Cleaned the clogged chiller filter and restored coolant flow.');
  const lessons = dialog.getByLabel(/lessons/i);
  if (await lessons.count()) await lessons.first().fill('Check chiller filter at every PM.');
  await dialog.getByRole('button', { name: /submit/i }).click();
  const reason = dialog.getByLabel(/reason/i);
  if (await reason.count() && await reason.first().isVisible().catch(() => false)) {
    await reason.first().fill('Separate confirmed occurrence.');
    await dialog.getByRole('button', { name: /submit/i }).click();
  }
}

// 5. QA lead: review and approve; names, incident link, summary updated.
await step('5 qa: approve case with names and links', async () => {
  const { ctx, page } = await session('qa@demo.local');
  const badgeEl = page.getByRole('navigation', { name: 'Main' }).getByLabel(/pending/).first();
  await badgeEl.waitFor({ timeout: 15000 });
  const sidebarBadge = await badgeEl.textContent();
  await page.getByText(/Review case for/).first().click();
  await page.getByRole('link', { name: uploadedId }).first().waitFor();
  await page.getByText(/Plant Engineer/).first().waitFor();
  await page.getByRole('button', { name: 'Approve' }).click();
  await page.getByText(/Approved by QA Lead/).first().waitFor();
  await page.getByRole('link', { name: uploadedId }).first().click();
  await page.getByText('Case approved', { exact: true }).first().waitFor({ timeout: 30000 });
  await ctx.close();
  return 'sidebar pending badges: ' + sidebarBadge;
});

// 6. Engineer: analyse a similar incident -> approved case recalled.
await step('6 engineer: similar incident recalls approved case', async () => {
  const { ctx, page } = await session('engineer@demo.local');
  await nav(page, 'Incidents');
  await page.getByRole('row', { name: /INC-009/ }).click();
  await Promise.all([page.waitForResponse((r) => r.url().endsWith('/analyze') && r.request().method() === 'POST', { timeout: 120000 }),
                     page.getByRole('button', { name: /run rca analysis/i }).click()]);
  await page.getByRole('heading', { name: 'Ranked hypotheses' }).waitFor({ timeout: 90000 });
  await page.waitForTimeout(500);
  const similar = await page.locator('section', { hasText: 'Similar Past Cases' }).first().innerText();
  await ctx.close();
  if (!similar.includes('CASE-') && !similar.toLowerCase().includes('qa-approved')) throw new Error('approved case not recalled');
  return 'recalled';
});

// 6b. QA lead: edit the approved case (new version kept), then retire it; it is no longer recalled.
await step('6b qa: edit approved case, retire, not recalled', async () => {
  const { ctx, page } = await session('qa@demo.local');
  await nav(page, 'Cases');
  await page.getByLabel('Case status').selectOption('approved');
  await page.locator('a[href^="/cases/CASE-"]').first().click();
  await page.getByRole('button', { name: 'Edit approved case' }).click();
  await page.getByLabel('Lessons learned').fill('Check chiller filter at every PM and log the pressure drop.');
  await page.getByLabel('Reason *').fill('Add the pressure-drop check');
  await page.getByRole('button', { name: 'Save new version' }).click();
  await page.getByText(/Case · version 2/).waitFor();
  await page.getByText(/Version 1 \(approved\)/).waitFor();
  const caseId = (await page.locator('h1').innerText()).trim();
  await page.getByRole('button', { name: 'Retire case' }).first().click();
  await page.getByLabel('Reason *').fill('Superseded by new chiller design');
  await page.getByRole('button', { name: 'Retire case' }).last().click();
  await page.getByText('This case is never recalled.', { exact: false }).waitFor();
  await ctx.close();
  const eng = await session('engineer@demo.local');
  await nav(eng.page, 'Incidents');
  await eng.page.getByRole('row', { name: /INC-009/ }).click();
  await eng.page.getByText('Analysis complete').waitFor({ timeout: 90000 });
  await Promise.all([eng.page.waitForResponse((r) => r.url().endsWith('/analyze') && r.request().method() === 'POST', { timeout: 120000 }),
                     eng.page.getByRole('button', { name: /re-run rca analysis/i }).click()]);
  await eng.page.waitForTimeout(500);
  const similar = await eng.page.locator('section', { hasText: 'Similar Past Cases' }).first().innerText();
  await eng.ctx.close();
  if (similar.includes(caseId)) throw new Error('retired case still recalled');
  return caseId + ' retired';
});

// 7. QA lead: run evaluations.
await step('7 qa: run evaluations', async () => {
  const { ctx, page } = await session('qa@demo.local');
  await nav(page, 'Evaluations');
  await page.getByRole('button', { name: /run evaluations/i }).click();
  await page.getByText(/Last run:/).waitFor({ timeout: 600000 });
  const fails = await page.getByText(/· threshold/).filter({ hasText: /^Fail/ }).count();
  const passes = await page.getByText(/^Pass · threshold/).count();
  await ctx.close();
  if (fails) throw new Error(fails + ' failing metrics');
  return passes + ' metrics pass';
});

// 8. Viewer: read only.
await step('8 viewer: read only', async () => {
  const { ctx, page } = await session('viewer@demo.local');
  const links = await page.getByRole('navigation', { name: 'Main' }).innerText();
  if (/Upload data|Users/.test(links)) throw new Error('viewer sees upload/users');
  await nav(page, 'Incidents');
  await page.getByRole('row', { name: new RegExp(uploadedId) }).click();
  await page.locator('#rca-draft').waitFor({ timeout: 30000 });
  if (await page.getByRole('button', { name: /run rca analysis|save version|propose case/i }).count()) throw new Error('viewer sees mutation buttons');
  if (!(await page.locator('#rca-draft').getAttribute('readonly') !== null)) throw new Error('draft editable');
  await page.goto(BASE + '/upload');
  await page.getByText('Your role cannot open this page.').waitFor();
  await ctx.close();
});

await browser.close();
fs.writeFileSync('walk-results.json', JSON.stringify(results, null, 2));
console.log(`\n${results.filter((r) => r.passed).length}/${results.length} steps passed`);
process.exit(results.every((r) => r.passed) ? 0 : 1);
