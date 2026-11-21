import fs from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';

const require = createRequire(import.meta.url);

function resolvePlaywright() {
  const candidates = [];
  if (process.env.PLAYWRIGHT_NODE_MODULES) {
    candidates.push(path.join(process.env.PLAYWRIGHT_NODE_MODULES, 'playwright'));
    candidates.push(process.env.PLAYWRIGHT_NODE_MODULES);
  }
  if (process.env.NODE_PATH) {
    for (const entry of process.env.NODE_PATH.split(path.delimiter)) {
      if (entry) {
        candidates.push(path.join(entry, 'playwright'));
      }
    }
  }
  for (const modPath of candidates) {
    if (fs.existsSync(modPath)) {
      return require(modPath);
    }
  }
  return require('playwright');
}

function resolveExecutablePath(chromium) {
  try {
    const defaultPath = chromium.executablePath();
    if (defaultPath && fs.existsSync(defaultPath)) {
      return undefined;
    }
  } catch {
    // Fall through to explicit binary discovery.
  }
  const localAppData = process.env.LOCALAPPDATA || '';
  const fallbacks = [
    process.env.KANE_CLI_CHROME_PATH,
    path.join(localAppData, 'ms-playwright', 'chromium-1248', 'chrome-win64', 'chrome.exe'),
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  ].filter(Boolean);
  for (const candidate of fallbacks) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  return undefined;
}

async function findFirstLocator(page, selectors, requireVisible = false) {
  for (const selector of selectors) {
    const loc = page.locator(selector).first();
    const count = await loc.count();
    if (count > 0) {
      if (!requireVisible) {
        return { selector, loc };
      }
      if (await loc.isVisible()) {
        return { selector, loc };
      }
    }
  }
  return null;
}

async function runAction(page, action, pendingRequests) {
  const timeoutMs = action.timeoutMs ?? 5000;
  switch (action.type) {
    case 'wait_ms': {
      await page.waitForTimeout(action.ms ?? 250);
      if (pendingRequests) {
        const settleDeadline = Date.now() + 5000;
        while (pendingRequests.size > 0 && Date.now() < settleDeadline) {
          await page.waitForTimeout(30);
        }
      }
      return { type: 'wait_ms', ok: true };
    }
    case 'wait_for_selector': {
      await page.waitForSelector(action.selector, {
        state: action.state ?? 'visible',
        timeout: timeoutMs,
      });
      return { type: 'wait_for_selector', selector: action.selector, ok: true };
    }
    case 'wait_for_any': {
      const deadline = Date.now() + timeoutMs;
      while (Date.now() < deadline) {
        const found = await findFirstLocator(page, action.selectors || [], Boolean(action.visible));
        if (found) {
          return { type: 'wait_for_any', matched: found.selector, ok: true };
        }
        await page.waitForTimeout(100);
      }
      if (action.optional) {
        return { type: 'wait_for_any', matched: null, ok: false };
      }
      throw new Error(`No selector matched within ${timeoutMs}ms: ${(action.selectors || []).join(', ')}`);
    }
    case 'press': {
      await page.keyboard.press(action.key);
      return { type: 'press', key: action.key, ok: true };
    }
    case 'click_first': {
      const found = await findFirstLocator(page, action.selectors || [], action.visible ?? true);
      if (!found) {
        if (action.optional) {
          return { type: 'click_first', clicked: null, ok: false };
        }
        throw new Error(`No clickable selector matched: ${(action.selectors || []).join(', ')}`);
      }
      if (action.skipIfDisabled && (await found.loc.isDisabled())) {
        return { type: 'click_first', clicked: found.selector, disabled: true, ok: true };
      }
      await found.loc.click({ timeout: timeoutMs, force: Boolean(action.force) });
      return { type: 'click_first', clicked: found.selector, disabled: false, ok: true };
    }
    case 'click_text': {
      const patterns = action.patterns || [];
      for (const pattern of patterns) {
        const regex = new RegExp(pattern, 'i');
        const btn = page.getByRole('button', { name: regex }).first();
        if ((await btn.count()) > 0 && (await btn.isVisible())) {
          await btn.click({ timeout: timeoutMs });
          return { type: 'click_text', matched: pattern, role: 'button', ok: true };
        }
        const tab = page.getByRole('tab', { name: regex }).first();
        if ((await tab.count()) > 0 && (await tab.isVisible())) {
          await tab.click({ timeout: timeoutMs });
          return { type: 'click_text', matched: pattern, role: 'tab', ok: true };
        }
        const txt = page.getByText(regex).first();
        if ((await txt.count()) > 0 && (await txt.isVisible())) {
          await txt.click({ timeout: timeoutMs });
          return { type: 'click_text', matched: pattern, role: 'text', ok: true };
        }
      }
      if (action.optional) {
        return { type: 'click_text', matched: null, ok: false };
      }
      throw new Error(`No clickable text matched: ${patterns.join(', ')}`);
    }
    case 'fill_first': {
      const found = await findFirstLocator(page, action.selectors || [], action.visible ?? true);
      if (!found) {
        if (action.optional) {
          return { type: 'fill_first', filled: null, ok: false };
        }
        throw new Error(`No fillable selector matched: ${(action.selectors || []).join(', ')}`);
      }
      let nextVal = String(action.value ?? '');
      const inputType = await found.loc.evaluate((el) => (el.getAttribute('type') || '').toLowerCase());
      if (inputType === 'datetime-local' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?Z$/.test(nextVal)) {
        nextVal = nextVal.slice(0, 16);
      }
      await found.loc.fill(nextVal, { timeout: timeoutMs });
      return { type: 'fill_first', filled: found.selector, ok: true };
    }
    case 'select_first': {
      const found = await findFirstLocator(page, action.selectors || [], action.visible ?? true);
      if (!found) {
        if (action.optional) {
          return { type: 'select_first', selected: null, ok: false };
        }
        throw new Error(`No select selector matched: ${(action.selectors || []).join(', ')}`);
      }
      await found.loc.selectOption(String(action.value ?? ''), { timeout: timeoutMs });
      return { type: 'select_first', selected: found.selector, value: String(action.value ?? ''), ok: true };
    }
    case 'set_input_value': {
      const found = await findFirstLocator(page, action.selectors || [], false);
      if (!found) {
        if (action.optional) {
          return { type: 'set_input_value', updated: null, ok: false };
        }
        throw new Error(`No input selector matched: ${(action.selectors || []).join(', ')}`);
      }
      const nextVal = String(action.value ?? '');
      await found.loc.evaluate((el, val) => {
        const prev = el.value;
        const proto = el.tagName === 'TEXTAREA'
          ? window.HTMLTextAreaElement.prototype
          : el.tagName === 'SELECT'
            ? window.HTMLSelectElement.prototype
            : window.HTMLInputElement.prototype;
        const descriptor = Object.getOwnPropertyDescriptor(proto, 'value');
        if (descriptor && descriptor.set) {
          descriptor.set.call(el, val);
        } else {
          el.value = val;
        }
        const tracker = el._valueTracker;
        if (tracker && typeof tracker.setValue === 'function') {
          tracker.setValue(prev === val ? '' : prev);
        }
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
      }, nextVal);
      return { type: 'set_input_value', updated: found.selector, value: nextVal, ok: true };
    }
    case 'check_first': {
      const found = await findFirstLocator(page, action.selectors || [], false);
      if (!found) {
        if (action.optional) {
          return { type: 'check_first', selector: null, ok: false };
        }
        throw new Error(`No checkbox/toggle selector matched: ${(action.selectors || []).join(', ')}`);
      }
      const desired = Boolean(action.checked);
      const isInput = await found.loc.evaluate((el) => el.tagName === 'INPUT' && el.type === 'checkbox');
      if (isInput) {
        const current = await found.loc.isChecked();
        if (current !== desired) {
          await found.loc.click({ timeout: timeoutMs });
        }
      } else {
        const ariaChecked = await found.loc.getAttribute('aria-checked');
        if (ariaChecked !== null) {
          const current = ariaChecked === 'true';
          if (current !== desired) {
            await found.loc.click({ timeout: timeoutMs });
          }
        } else {
          await found.loc.click({ timeout: timeoutMs });
        }
      }
      return { type: 'check_first', selector: found.selector, checked: desired, ok: true };
    }
    case 'eval': {
      const rawScript = String(action.script || '').trim();
      const expr = /^(\(|async\b|[A-Za-z_$][A-Za-z0-9_$]*\s*=>)/.test(rawScript)
        ? `(${rawScript})()`
        : rawScript;
      const value = await page.evaluate(expr);
      return { type: 'eval', value: value === undefined ? null : value, ok: true };
    }
    case 'inspect_houdini': {
      const value = await page.evaluate(() => {
        const root = document.documentElement;
        const cs = getComputedStyle(root);
        const bodyCs = document.body ? getComputedStyle(document.body) : cs;
        const pick = (name) => (cs.getPropertyValue(name) || bodyCs.getPropertyValue(name) || '').trim();
        return {
          rhythm_bpm: pick('--rhythm-bpm'),
          overwhelm_index: pick('--overwhelm-index'),
          focus_depth: pick('--focus-depth'),
          cadence_color: pick('--cadence-color'),
          lattice_phase: pick('--lattice-phase'),
          has_register_property: typeof CSS !== 'undefined' && typeof CSS.registerProperty === 'function',
          has_paint_worklet: typeof CSS !== 'undefined' && Boolean(CSS.paintWorklet),
        };
      });
      return { type: 'inspect_houdini', value, ok: true };
    }
    case 'inspect_dom': {
      const value = await page.evaluate(() => {
        const rootEl = document.querySelector('#root') || document.body;
        const buttons = Array.from(document.querySelectorAll('button')).map((b) => (b.innerText || '').trim());
        const inputs = Array.from(document.querySelectorAll('input, textarea, select')).map((el) => ({
          tag: el.tagName.toLowerCase(),
          type: el.getAttribute('type') || '',
          name: el.getAttribute('name') || '',
          placeholder: el.getAttribute('placeholder') || '',
          ariaLabel: el.getAttribute('aria-label') || '',
          disabled: Boolean(el.disabled),
        }));
        return {
          title: document.title,
          innerText: document.body ? document.body.innerText : '',
          htmlLength: document.documentElement ? document.documentElement.innerHTML.length : 0,
          scrollWidth: document.documentElement ? document.documentElement.scrollWidth : 0,
          innerWidth: window.innerWidth,
          svgCount: document.querySelectorAll('svg').length,
          canvasCount: document.querySelectorAll('canvas').length,
          rootChildCount: rootEl ? rootEl.children.length : 0,
          buttonTexts: buttons,
          inputs,
        };
      });
      return { type: 'inspect_dom', value, ok: true };
    }
    default:
      throw new Error(`Unknown action type: ${action.type}`);
  }
}

async function main() {
  const chunks = [];
  for await (const chunk of process.stdin) {
    chunks.push(chunk);
  }
  const raw = Buffer.concat(chunks).toString('utf-8').trim();
  const spec = raw ? JSON.parse(raw) : {};
  const { chromium } = resolvePlaywright();
  const executablePath = resolveExecutablePath(chromium);
  const launchOpts = { headless: true };
  if (executablePath) {
    launchOpts.executablePath = executablePath;
  }

  let browser;
  const result = {
    ok: false,
    statusCode: null,
    executablePath: executablePath || chromium.executablePath(),
    pageErrors: [],
    consoleErrors: [],
    failedRequests: [],
    responses: [],
    stepResults: [],
    dom: null,
    houdini: null,
    error: null,
  };

  try {
    browser = await chromium.launch(launchOpts);
    const context = await browser.newContext({
      viewport: spec.viewport || { width: 1280, height: 800 },
      reducedMotion: spec.reducedMotion || 'no-preference',
    });
    const page = await context.newPage();

    if (spec.disablePaintWorklet) {
      await page.addInitScript(() => {
        try {
          Object.defineProperty(CSS, 'paintWorklet', {
            configurable: true,
            get() {
              return undefined;
            },
          });
        } catch {
          // Fallback if property is non-configurable.
        }
      });
    }
    if (spec.initScript) {
      await page.addInitScript(spec.initScript);
    }

    const pendingRequests = new Set();
    page.on('request', (req) => {
      pendingRequests.add(req);
    });
    page.on('requestfinished', (req) => {
      pendingRequests.delete(req);
    });
    page.on('pageerror', (err) => {
      result.pageErrors.push(String(err && err.stack ? err.stack : err));
    });
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        result.consoleErrors.push(msg.text());
      }
    });
    page.on('requestfailed', (req) => {
      pendingRequests.delete(req);
      result.failedRequests.push({
        url: req.url(),
        method: req.method(),
        failure: req.failure()?.errorText || 'unknown',
      });
    });
    page.on('response', (res) => {
      result.responses.push({
        url: res.url(),
        method: res.request().method(),
        status: res.status(),
      });
    });

    if (spec.htmlContent) {
      await page.setContent(spec.htmlContent, { waitUntil: 'load' });
      result.statusCode = 200;
    } else if (spec.url) {
      const resp = await page.goto(spec.url, {
        waitUntil: spec.waitUntil || 'networkidle',
        timeout: spec.timeoutMs || 30000,
      });
      result.statusCode = resp ? resp.status() : null;
      await page.waitForTimeout(spec.settleMs ?? 350);
    }

    for (const action of spec.actions || []) {
      const stepOut = await runAction(page, action, pendingRequests);
      result.stepResults.push(stepOut);
    }

    const settleDeadline = Date.now() + 5000;
    while (pendingRequests.size > 0 && Date.now() < settleDeadline) {
      await page.waitForTimeout(30);
    }

    result.dom = (await runAction(page, { type: 'inspect_dom' })).value;
    result.houdini = (await runAction(page, { type: 'inspect_houdini' })).value;
    result.ok = true;
    await context.close();
  } catch (err) {
    result.error = String(err && err.stack ? err.stack : err);
    result.ok = false;
  } finally {
    if (browser) {
      await browser.close();
    }
  }

  process.stdout.write(JSON.stringify(result));
  if (!result.ok) {
    process.exitCode = 1;
  }
}

main();
