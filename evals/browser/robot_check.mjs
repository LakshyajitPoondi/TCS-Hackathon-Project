// Headless check of the login page and RcaRobot against frontend_design.md section 8 / section 11.
// Needs the app on http://localhost:5173 with DEMO_USERS_ENABLED=true (development). Usage: node robot_check.mjs
import { chromium } from 'playwright-core';
import fs from 'node:fs';

const BASE = 'http://localhost:5173';
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const results = [];
const check = (name, passed, note = '') => { results.push({ name, passed: !!passed, note }); console.log(passed ? 'PASS' : 'FAIL', name, note); };
fs.mkdirSync('shots', { recursive: true });
const browser = await chromium.launch({ executablePath: CHROME, headless: true });

// Read the current translate/rotate/scale of a robot part from its computed transform matrix.
const partState = (page, part) => page.evaluate((p) => {
  const el = document.querySelector(`[data-part="${p}"]`);
  const m = new DOMMatrixReadOnly(getComputedStyle(el).transform === 'none' ? undefined : getComputedStyle(el).transform);
  return { x: m.m41, y: m.m42, rotate: Math.atan2(m.m12, m.m11) * 180 / Math.PI, scaleY: Math.hypot(m.m21, m.m22) };
}, part);
const robotAttr = (page, name) => page.getAttribute('[aria-label="Animated assistant robot"]', name);

async function open(options = {}) {
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 900 }, ...options });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => { if (m.type() === 'error' && !m.text().startsWith('Failed to load resource')) errors.push(m.text()); });
  // Failed requests are reported by URL; the deliberate wrong-password login (401) is expected.
  page.on('response', (r) => { if (r.status() >= 400 && !(r.status() === 401 && r.url().endsWith('/api/auth/login'))) errors.push(`${r.status()} ${r.url()}`); });
  await page.addInitScript(() => {
    window.__cls = 0; window.__robotShift = false;
    new PerformanceObserver((list) => { for (const e of list.getEntries()) if (!e.hadRecentInput) {
      window.__cls += e.value;
      if ((e.sources || []).some((src) => src.node && src.node.closest && src.node.closest('[aria-label$="robot"]'))) window.__robotShift = true;
    } }).observe({ type: 'layout-shift', buffered: true });
    window.__longTasks = [];
    new PerformanceObserver((list) => { for (const e of list.getEntries()) window.__longTasks.push(e.duration); }).observe({ type: 'longtask', buffered: true });
  });
  await page.goto(BASE + '/login');
  await page.waitForSelector('[aria-label="Animated assistant robot"][data-robot-state]', { timeout: 30000 });
  return { ctx, page, errors };
}

{
  const { ctx, page, errors } = await open();
  // Lazy chunk: the robot module is fetched separately from the main bundle.
  const scripts = await page.evaluate(() => performance.getEntriesByType('resource').map((r) => r.name).filter((n) => /\.(js|tsx|ts)(\?|$)/.test(n)));
  check('robot lazy-loaded as its own module', scripts.some((s) => /RcaRobot/.test(s)), scripts.filter((s) => /RcaRobot|robot/i.test(s)).map((s) => s.split('/').pop()).join(', '));
  await page.waitForTimeout(800);
  check('no layout shift while the robot loads (robot never shifts, page CLS < 0.01)', !(await page.evaluate(() => window.__robotShift)) && (await page.evaluate(() => window.__cls)) < 0.01,
        'CLS=' + (await page.evaluate(() => window.__cls)).toFixed(4));
  const box = await page.locator('[aria-label="Animated assistant robot"]').boundingBox();
  check('robot 340 px wide on desktop', Math.round(box.width) === 340, JSON.stringify({ w: box.width, h: box.height }));
  await page.screenshot({ path: 'shots/login-desktop.png' });

  // Cursor tracking with lag hierarchy: 120 ms after a move, eyes have covered more of their range than head, head more than body.
  await page.mouse.move(683, 450); await page.waitForTimeout(1200);
  await page.mouse.move(1360, 450);
  await page.waitForTimeout(120);
  const [eyes, head, body] = [await partState(page, 'eyes'), await partState(page, 'head'), await partState(page, 'body')];
  const fr = { eyes: eyes.x / 10, head: head.x / 8, body: body.rotate / 2.5 };
  check('eyes, head and body follow the cursor with lagged springs (eyes > head > body)', fr.eyes > fr.head && fr.head > fr.body && fr.body > 0, JSON.stringify(fr));
  await page.waitForTimeout(1500);
  const settled = [await partState(page, 'eyes'), await partState(page, 'head'), await partState(page, 'body')];
  check('pose settles toward cursor (eyes ~+10 px, head tilt > 0, body lean > 0)', settled[0].x > 6 && settled[1].rotate > 2 && settled[2].rotate > 1,
        JSON.stringify(settled.map((s) => ({ x: +s.x.toFixed(1), r: +s.rotate.toFixed(2) }))));

  // FPS and input lag while the pointer moves and the user types.
  const fps = await page.evaluate(() => new Promise((resolve) => { let n = 0; const t0 = performance.now(); const f = () => { n++; if (performance.now() - t0 < 2000) requestAnimationFrame(f); else resolve(n / 2); }; requestAnimationFrame(f); }));
  check('animation loop runs at ~60 fps', fps >= 50, fps + ' fps');

  // Blink within 6 s.
  const minScale = await page.evaluate(() => new Promise((resolve) => {
    let min = 1; const t0 = performance.now();
    const f = () => { const el = document.querySelector('[data-part="eyeL"]'); const m = new DOMMatrixReadOnly(getComputedStyle(el).transform === 'none' ? undefined : getComputedStyle(el).transform);
      min = Math.min(min, Math.hypot(m.m21, m.m22)); if (performance.now() - t0 < 6500) requestAnimationFrame(f); else resolve(min); };
    requestAnimationFrame(f);
  }));
  check('blinks (eye scaleY dips below 0.5 within 6.5 s)', minScale < 0.5, 'min scaleY ' + minScale.toFixed(2));

  // Idle look-around after 4 s without pointer movement.
  await page.waitForTimeout(500);
  const idle = await robotAttr(page, 'data-robot-idle');
  const a = await partState(page, 'eyes'); await page.waitForTimeout(2600); const b = await partState(page, 'eyes');
  check('idle look-around after 4 s without movement', idle === 'true' && Math.hypot(a.x - b.x, a.y - b.y) > 0.5, `idle=${idle} moved=${Math.hypot(a.x - b.x, a.y - b.y).toFixed(2)}`);

  // Email focus: watchingEmail, eyes follow the caret.
  await page.locator('#auth-email').click();
  check('email focus -> watchingEmail', (await robotAttr(page, 'data-robot-state')) === 'watchingEmail');
  await page.waitForTimeout(500); const e0 = await partState(page, 'eyes');
  await page.evaluate(() => { window.__longTasks = []; });
  const t0 = Date.now(); await page.keyboard.type('engineer@demo.local', { delay: 15 }); const typing = Date.now() - t0;
  await page.waitForTimeout(500); const e1 = await partState(page, 'eyes');
  check('eyes follow the caret while typing', e1.x > e0.x + 2, `${e0.x.toFixed(1)} -> ${e1.x.toFixed(1)}`);
  const long = await page.evaluate(() => window.__longTasks.filter((d) => d > 50).length);
  check('no input lag while typing (value correct, no long tasks > 50 ms)', (await page.inputValue('#auth-email')) === 'engineer@demo.local' && long === 0, `typing ${typing} ms, long tasks ${long}`);

  // Password: privacy (arms cover the visor), show password: peeking, blur: back to tracking.
  await page.locator('#auth-password').click(); await page.waitForTimeout(700);
  const armL = await partState(page, 'armL'), armR = await partState(page, 'armR');
  check('password focus -> privacy, arms rise to cover the visor', (await robotAttr(page, 'data-robot-state')) === 'privacy' && armL.rotate < -120 && armR.rotate > 120,
        `armL ${armL.rotate.toFixed(0)} deg, armR ${armR.rotate.toFixed(0)} deg, eyes ${await robotAttr(page, 'data-eye-mode')}`);
  await page.screenshot({ path: 'shots/robot-privacy.png', clip: { ...(await page.locator('[aria-label="Animated assistant robot"]').boundingBox()) } });
  await page.getByRole('button', { name: 'Show password' }).click(); await page.waitForTimeout(700);
  const peekR = await partState(page, 'armR'), eyeR = await partState(page, 'eyeR'), eyeL = await partState(page, 'eyeL');
  check('show password -> peeking (one arm lowers, one eye opens)', (await robotAttr(page, 'data-robot-state')) === 'peeking' && peekR.rotate < armR.rotate - 15 && eyeR.scaleY > 0.8 && eyeL.scaleY < 0.3,
        `armR ${peekR.rotate.toFixed(0)} deg, eyeR ${eyeR.scaleY.toFixed(2)}, eyeL ${eyeL.scaleY.toFixed(2)}`);
  await page.screenshot({ path: 'shots/robot-peeking.png', clip: { ...(await page.locator('[aria-label="Animated assistant robot"]').boundingBox()) } });
  await page.getByRole('button', { name: 'Hide password' }).click(); await page.waitForTimeout(200);
  check('hide password -> privacy', (await robotAttr(page, 'data-robot-state')) === 'privacy');
  await page.locator('h1').click(); await page.waitForTimeout(700);
  check('password blur -> tracking, arms lower', (await robotAttr(page, 'data-robot-state')) === 'tracking' && (await partState(page, 'armL')).rotate > -20);

  // Wrong password: thinking, then error (head shake, red eyes, input shake), back to tracking after 1.5 s.
  await page.locator('#auth-password').fill('definitely-wrong-password');
  const seen = page.evaluate(() => new Promise((resolve) => { const s = []; const el = document.querySelector('[aria-label="Animated assistant robot"]');
    const obs = new MutationObserver(() => { const v = el.getAttribute('data-robot-state'); if (s.at(-1) !== v) s.push(v); });
    obs.observe(el, { attributes: true, attributeFilter: ['data-robot-state'] }); setTimeout(() => { obs.disconnect(); resolve(s); }, 4000); }));
  const shakeSeen = page.evaluate(() => new Promise((resolve) => { const obs = new MutationObserver(() => { if (document.querySelector('.rr-input-shake')) { obs.disconnect(); resolve(true); } });
    obs.observe(document.body, { subtree: true, attributes: true, attributeFilter: ['class'] }); setTimeout(() => resolve(false), 4000); }));
  await page.getByRole('button', { name: /open dashboard/i }).click();
  await page.waitForFunction(() => document.querySelector('[aria-label="Animated assistant robot"]')?.getAttribute('data-robot-state') === 'error', null, { timeout: 10000 });
  const headShake = []; for (let i = 0; i < 10; i++) { headShake.push((await partState(page, 'head')).x); await page.waitForTimeout(30); }
  const states = await seen;
  check('submit -> thinking, login error -> error -> tracking', states.includes('thinking') && states.includes('error') && states.at(-1) === 'tracking', states.join(' > '));
  check('error: head shakes and the input shakes', Math.max(...headShake) - Math.min(...headShake) > 6 && await shakeSeen, `head x range ${(Math.max(...headShake) - Math.min(...headShake)).toFixed(1)}`);
  await page.waitForTimeout(1200);
  check('error text shown under the inputs', await page.locator('#auth-error').isVisible(), await page.locator('#auth-error').innerText());

  // Easter egg: click the head -> giggle eyes.
  const headBox = await page.locator('[data-part="head"]').boundingBox();
  await page.mouse.click(headBox.x + headBox.width / 2, headBox.y + 20); await page.waitForTimeout(100);
  check('click on head -> giggle eyes', (await robotAttr(page, 'data-eye-mode')) === 'giggle');

  // Sign in / Sign up toggle and demo profiles.
  await page.getByRole('tab', { name: 'Sign up' }).click();
  check('sign-up toggle shows the request-access form', await page.locator('#auth-name').isVisible() && (await page.locator('h1').innerText()) === 'Request access');
  await page.getByRole('tab', { name: 'Sign in' }).click();
  const demoButtons = await page.getByRole('button', { name: /^(Administrator|Plant engineer|QA lead|Viewer)$/ }).count();
  await page.getByRole('button', { name: 'Plant engineer' }).click();
  check('4 demo profile buttons fill email AND password', demoButtons === 4 && (await page.inputValue('#auth-email')) === 'engineer@demo.local' && (await page.inputValue('#auth-password')).length >= 10);
  await page.waitForTimeout(150);
  check('demo profile -> right-arm wave', (await partState(page, 'armR')).rotate < -40, (await partState(page, 'armR')).rotate.toFixed(0) + ' deg');
  check('Engine online + footer status badges', await page.getByText('Engine online').isVisible() && await page.getByText(/RCA engine v/).isVisible() && await page.getByText('Data source connected').isVisible());

  // Success: thinking -> success (happy eyes, hop) -> navigate after ~900 ms.
  await page.waitForTimeout(1600);
  const started = Date.now();
  await page.getByRole('button', { name: /open dashboard/i }).click();
  await page.waitForFunction(() => document.querySelector('[aria-label="Animated assistant robot"]')?.getAttribute('data-robot-state') === 'success', null, { timeout: 15000 });
  const happy = await robotAttr(page, 'data-eye-mode');
  await page.waitForURL(BASE + '/', { timeout: 15000 });
  check('login success -> happy eyes, hold ~900 ms, then dashboard', happy === 'happy' && Date.now() - started >= 900, `${Date.now() - started} ms`);
  check('no console errors on the login page', errors.length === 0, errors.join(' | '));
  await ctx.close();
}

// Reduced motion: no head movement, eyes within ±4 px, no float animation.
{
  const { ctx, page } = await open({ reducedMotion: 'reduce' });
  await page.mouse.move(1360, 100); await page.waitForTimeout(900);
  const eyes = await partState(page, 'eyes'), head = await partState(page, 'head');
  const floatAnim = await page.evaluate(() => getComputedStyle(document.querySelector('.rr-float')).animationName);
  check('reduced motion: eyes ≤ 4 px, head still, no float', (await robotAttr(page, 'data-reduced')) === 'true' && Math.abs(eyes.x) <= 4.01 && Math.abs(head.x) < 0.01 && Math.abs(head.rotate) < 0.01 && floatAnim === 'none',
        `eyes ${eyes.x.toFixed(2)}, head ${head.x.toFixed(2)}/${head.rotate.toFixed(2)}, float ${floatAnim}`);
  await ctx.close();
}

// Touch device at 375 px: touchmove tracks, touchend returns to centre, 200 px robot, no horizontal scroll.
{
  const { ctx, page } = await open({ viewport: { width: 375, height: 812 }, hasTouch: true, isMobile: true });
  const box = await page.locator('[aria-label="Animated assistant robot"]').boundingBox();
  const scroll = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  check('mobile: 200 px robot, no horizontal scroll at 375 px', Math.round(box.height) === 200 && scroll <= 0, `robot ${box.width}x${box.height}, overflow ${scroll}`);
  await page.evaluate(() => { const t = new Touch({ identifier: 1, target: document.body, clientX: 370, clientY: 120 });
    window.dispatchEvent(new TouchEvent('touchmove', { touches: [t], changedTouches: [t] })); });
  await page.waitForTimeout(900);
  const moved = await partState(page, 'eyes');
  await page.evaluate(() => window.dispatchEvent(new TouchEvent('touchend', { touches: [], changedTouches: [] })));
  await page.waitForTimeout(400);
  const back = await partState(page, 'eyes');
  check('touch: eyes follow touchmove and return toward centre on touchend', moved.x > 3 && Math.abs(back.x) < Math.abs(moved.x), `${moved.x.toFixed(1)} -> ${back.x.toFixed(1)}`);
  await page.screenshot({ path: 'shots/login-mobile.png', fullPage: true });
  await ctx.close();
}

for (const width of [768, 1280, 1536]) {
  const ctx = await browser.newContext({ viewport: { width, height: 900 } });
  const page = await ctx.newPage(); await page.goto(BASE + '/login'); await page.waitForSelector('#auth-email');
  const scroll = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  check(`layout holds at ${width} px`, scroll <= 0, 'overflow ' + scroll);
  await ctx.close();
}

await browser.close();
fs.writeFileSync('robot-results.json', JSON.stringify(results, null, 2));
console.log(`\n${results.filter((r) => r.passed).length}/${results.length} checks passed`);
process.exit(results.every((r) => r.passed) ? 0 : 1);
