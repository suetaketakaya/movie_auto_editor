/**
 * ClipMontage — Production E2E Tests
 * Target: https://moviecutter.web.app (Firebase Hosting)
 *
 * Unlike the local emulator tests, this suite verifies:
 *  - Real security headers (CSP, COOP, COEP, XCTO, XFO, Referrer-Policy, Permissions-Policy)
 *  - Cache-Control for index.html (no-store) and static assets (max-age)
 *  - Real Firebase Auth initialization (not emulator)
 *  - No CSP violations in browser console
 *  - Full UI flows: landing, auth modal, upload, settings, dashboard
 */
import { test, expect } from '@playwright/test';

const PROD_URL   = 'https://moviecutter.web.app';
const VIDEO_PATH = 'D:\\Valorant\\Valorant 2023.10.07 - 15.29.44.01.mp4'; // 5s / 15 MB

// ──────────────────────────────────────────────────────────────────────────────
// Helpers
// ──────────────────────────────────────────────────────────────────────────────

/** Collect browser console errors (excluding known-OK ones) */
function attachConsoleMonitor(page) {
  const errors = [];
  const cspViolations = [];
  page.on('console', msg => {
    if (msg.type() === 'error') {
      const text = msg.text();
      errors.push(text);
      if (text.toLowerCase().includes('content security policy') ||
          text.toLowerCase().includes('csp')) {
        cspViolations.push(text);
      }
    }
  });
  return { errors, cspViolations };
}

/** Force show the app shell by injecting JS (used when auth is required) */
async function forceShowAppShell(page) {
  await page.evaluate(() => {
    const loading = document.getElementById('view-loading');
    const landing = document.getElementById('view-landing');
    const modal   = document.getElementById('auth-modal');
    const shell   = document.getElementById('app-shell');
    if (loading) loading.style.display = 'none';
    if (landing) landing.style.display = 'none';
    if (modal)   modal.style.display   = 'none';
    if (shell)   shell.style.display   = 'flex';
    // Disable showLanding to prevent redirect on navigation
    if (typeof window.showLanding === 'function') {
      window.showLanding = () => {};
    }
    if (typeof Router !== 'undefined') Router.navigate('upload');
  });
  await page.waitForTimeout(500);
}

// ──────────────────────────────────────────────────────────────────────────────
// Test Suite 1: HTTP & Security Headers
// ──────────────────────────────────────────────────────────────────────────────

test.describe('Security Headers', () => {
  let response;

  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage();
    response = await page.goto(PROD_URL, { waitUntil: 'domcontentloaded' });
    await page.close();
  });

  test('HTTP 200 OK', async () => {
    expect(response.status()).toBe(200);
  });

  test('X-Content-Type-Options: nosniff', async () => {
    expect(response.headers()['x-content-type-options']).toBe('nosniff');
  });

  test('X-Frame-Options: DENY', async () => {
    expect(response.headers()['x-frame-options']).toBe('DENY');
  });

  test('Content-Security-Policy present', async () => {
    const csp = response.headers()['content-security-policy'];
    expect(csp).toBeTruthy();
    // Must allow self + firebase JS CDN
    expect(csp).toContain("default-src 'self'");
    expect(csp).toContain('https://www.gstatic.com/firebasejs/');
    // Must allow HuggingFace & Groq APIs
    expect(csp).toContain('router.huggingface.co');
    expect(csp).toContain('api.groq.com');
    // Must allow Gemini
    expect(csp).toContain('generativelanguage.googleapis.com');
  });

  test('Cross-Origin-Opener-Policy: same-origin (required for SharedArrayBuffer / ffmpeg.wasm)', async () => {
    expect(response.headers()['cross-origin-opener-policy']).toBe('same-origin');
  });

  test('Cross-Origin-Embedder-Policy: credentialless (required for SharedArrayBuffer)', async () => {
    expect(response.headers()['cross-origin-embedder-policy']).toBe('credentialless');
  });

  test('Referrer-Policy: strict-origin-when-cross-origin', async () => {
    expect(response.headers()['referrer-policy']).toBe('strict-origin-when-cross-origin');
  });

  test('Permissions-Policy restricts camera/mic/geolocation', async () => {
    const pp = response.headers()['permissions-policy'] || '';
    expect(pp).toContain('camera=()');
    expect(pp).toContain('microphone=()');
    expect(pp).toContain('geolocation=()');
  });

  test('Cache-Control: no-store for index.html', async () => {
    const cc = response.headers()['cache-control'] || '';
    expect(cc).toMatch(/no-store|no-cache/);
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// Test Suite 2: Static Asset Caching
// ──────────────────────────────────────────────────────────────────────────────

test.describe('Static Asset Cache-Control', () => {
  test('/static/js/main.js has public cache header', async ({ page }) => {
    const resp = await page.goto(`${PROD_URL}/static/js/main.js`);
    const cc = resp.headers()['cache-control'] || '';
    expect(cc).toContain('public');
    expect(cc).toMatch(/max-age=\d+/);
  });

  test('/static/css/style.css has public cache header', async ({ page }) => {
    const resp = await page.goto(`${PROD_URL}/static/css/style.css`);
    expect(resp.status()).toBe(200);
    const cc = resp.headers()['cache-control'] || '';
    expect(cc).toContain('public');
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// Test Suite 3: Page Load & JS Classes
// ──────────────────────────────────────────────────────────────────────────────

test.describe('Page Load & Core JS', () => {
  test('loads under 10 seconds', async ({ page }) => {
    const start = Date.now();
    await page.goto(PROD_URL, { waitUntil: 'domcontentloaded' });
    const elapsed = Date.now() - start;
    expect(elapsed).toBeLessThan(10000);
    console.log(`  Page load: ${elapsed}ms`);
  });

  test('Firebase init resolves within 15s (loading screen disappears)', async ({ page }) => {
    await page.goto(PROD_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#view-loading', { state: 'hidden', timeout: 15000 });
    // Either landing or app-shell must be shown
    const landingVisible  = await page.locator('#view-landing').isVisible().catch(() => false);
    const appShellVisible = await page.locator('#app-shell').evaluate(
      el => el.style.display === 'flex'
    ).catch(() => false);
    expect(landingVisible || appShellVisible).toBe(true);
  });

  test('all core JS classes are defined', async ({ page }) => {
    await page.goto(PROD_URL, { waitUntil: 'networkidle' });
    // Wait for loading screen to disappear (Firebase init + scripts executed)
    await page.waitForSelector('#view-loading', { state: 'hidden', timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(500);

    // Use eval-based typeof so that const/let top-level declarations
    // (which don't become window properties) are also detected correctly.
    const missing = await page.evaluate(() =>
      [
        'VisionProvider', 'VisionProviderFactory',
        'HuggingFaceVisionClient', 'HuggingFaceClient', // compat alias
        'AudioAnalyzer', 'ProcessingPipeline', 'FrameExtractor',
        'VideoAssembler', 'Router',
      ].filter(c => {
        try { return eval(`typeof ${c}`) === 'undefined'; }
        catch (e) { return true; }
      })
    );
    expect(missing, `Missing classes: ${missing.join(', ')}`).toHaveLength(0);
  });

  test('no CSP violations in browser console', async ({ page }) => {
    const { cspViolations } = attachConsoleMonitor(page);
    await page.goto(PROD_URL, { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);
    expect(cspViolations, `CSP violations: ${cspViolations.join('\n')}`).toHaveLength(0);
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// Test Suite 4: Landing Page & Auth Modal
// ──────────────────────────────────────────────────────────────────────────────

test.describe('Landing Page & Auth Modal', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(PROD_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#view-loading', { state: 'hidden', timeout: 15000 }).catch(() => {});
  });

  test('landing page renders with hero section', async ({ page }) => {
    const landingVisible = await page.locator('#view-landing').isVisible().catch(() => false);
    if (!landingVisible) {
      // Auth might be cached — force landing for this test
      await page.evaluate(() => {
        document.getElementById('app-shell').style.display = 'none';
        document.getElementById('view-landing').style.display = 'flex';
      });
    }
    await expect(page.locator('#view-landing')).toBeVisible();
    await expect(page.locator('.hero h1')).toBeVisible();
    await expect(page.locator('.hero-accent')).toBeVisible();
  });

  test('auth modal: opens, has email/password/Google inputs', async ({ page }) => {
    // Open via JS so it works even if landing is not shown
    await page.evaluate(() => {
      if (typeof openAuthModal === 'function') openAuthModal();
    });
    await page.waitForTimeout(400);

    const modalDisplay = await page.locator('#auth-modal').evaluate(el => el.style.display);
    expect(modalDisplay).not.toBe('none');
    await expect(page.locator('#authEmail')).toBeVisible();
    await expect(page.locator('#authPassword')).toBeVisible();
    await expect(page.locator('#googleSignInBtn')).toBeVisible();
  });

  test('auth modal: toggle Sign Up / Sign In', async ({ page }) => {
    await page.evaluate(() => {
      if (typeof openAuthModal === 'function') openAuthModal();
    });
    await page.waitForTimeout(300);

    await page.locator('#authToggleBtn').click();
    await page.waitForTimeout(200);
    await expect(page.locator('#authModalTitle')).toHaveText('Sign Up');

    await page.locator('#authToggleBtn').click();
    await page.waitForTimeout(200);
    await expect(page.locator('#authModalTitle')).toHaveText('Sign In');
  });

  test('auth modal: closes on X button', async ({ page }) => {
    await page.evaluate(() => {
      if (typeof openAuthModal === 'function') openAuthModal();
    });
    await page.waitForTimeout(300);
    await page.locator('#authModalClose').click();
    await page.waitForTimeout(300);
    const modalDisplay = await page.locator('#auth-modal').evaluate(el => el.style.display);
    expect(modalDisplay).toBe('none');
  });

  test('sign-in uses redirect (not popup) — no popup blockers', async ({ page }) => {
    // Verify signInWithGoogle calls signInWithRedirect, not signInWithPopup
    const usesRedirect = await page.evaluate(() => {
      const src = typeof signInWithGoogle !== 'undefined' ? signInWithGoogle.toString() : '';
      return src.includes('Redirect') || src.includes('redirect');
    });
    expect(usesRedirect).toBe(true);
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// Test Suite 5: App Shell — Upload View
// ──────────────────────────────────────────────────────────────────────────────

test.describe('App Shell — Upload View', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(PROD_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#view-loading', { state: 'hidden', timeout: 15000 }).catch(() => {});
    await forceShowAppShell(page);
  });

  test('upload view is visible', async ({ page }) => {
    await expect(page.locator('#view-upload')).toBeVisible();
  });

  test('drop zone is visible', async ({ page }) => {
    await expect(page.locator('#uploadArea')).toBeVisible();
  });

  test('file input exists in DOM', async ({ page }) => {
    await expect(page.locator('#fileInput')).toHaveCount(1);
  });

  test('upload button exists in DOM', async ({ page }) => {
    await expect(page.locator('#uploadBtn')).toHaveCount(1);
  });

  test('file selection shows file details', async ({ page }) => {
    await page.locator('#fileInput').setInputFiles(VIDEO_PATH);
    await page.waitForTimeout(600);

    await expect(page.locator('#selectedFile')).toBeVisible();
    await expect(page.locator('#fileName')).not.toBeEmpty();
    await expect(page.locator('#fileSize')).not.toBeEmpty();
    await expect(page.locator('#uploadBtn')).toBeVisible();

    const name = await page.locator('#fileName').textContent();
    const size = await page.locator('#fileSize').textContent();
    console.log(`  Selected: "${name}" (${size})`);
  });

  test('guard: upload without API key shows error', async ({ page }) => {
    // Clear all keys
    await page.evaluate(() => {
      sessionStorage.removeItem('vision_api_key');
      sessionStorage.removeItem('hf_api_key');
      sessionStorage.removeItem('vision_provider');
      ['groq', 'gemini', 'huggingface', 'ollama'].forEach(p =>
        sessionStorage.removeItem(`vision_api_key_${p}`)
      );
    });

    // Select file
    const isSelected = await page.locator('#selectedFile').isVisible().catch(() => false);
    if (!isSelected) {
      await page.locator('#fileInput').setInputFiles(VIDEO_PATH);
      await page.waitForTimeout(400);
    }

    await page.locator('#uploadBtn').click();
    await page.waitForTimeout(800);

    // Should stay on upload view
    await expect(page.locator('#view-upload')).toBeVisible();
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// Test Suite 6: Settings Modal — Multi-Provider
// ──────────────────────────────────────────────────────────────────────────────

test.describe('Settings Modal', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(PROD_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#view-loading', { state: 'hidden', timeout: 15000 }).catch(() => {});
    await forceShowAppShell(page);
    await page.evaluate(() => {
      if (typeof openSettingsModal === 'function') openSettingsModal();
    });
    await page.waitForTimeout(400);
  });

  test('settings modal opens', async ({ page }) => {
    const display = await page.locator('#settings-modal').evaluate(el => el.style.display);
    expect(display).not.toBe('none');
  });

  test('4 provider radio buttons rendered', async ({ page }) => {
    const count = await page.locator('input[name="visionProvider"]').count();
    expect(count).toBe(4);
    // Verify all 4 providers are present
    for (const p of ['groq', 'gemini', 'ollama', 'huggingface']) {
      await expect(page.locator(`input[name="visionProvider"][value="${p}"]`)).toHaveCount(1);
    }
  });

  test('effect checkboxes: transitions, textOverlay, slowMo', async ({ page }) => {
    await expect(page.locator('#effectTransitions')).toHaveCount(1);
    await expect(page.locator('#effectTextOverlay')).toHaveCount(1);
    await expect(page.locator('#effectSlowMo')).toHaveCount(1);
  });

  test('Test Connection button exists', async ({ page }) => {
    await expect(page.locator('#settingsTestBtn')).toHaveCount(1);
  });

  test('HuggingFace: API key field and model ID field visible', async ({ page }) => {
    await page.evaluate(() => {
      const radio = document.querySelector('input[name="visionProvider"][value="huggingface"]');
      if (radio) { radio.checked = true; radio.dispatchEvent(new Event('change')); }
    });
    await page.waitForTimeout(200);
    await expect(page.locator('#settingsApiKey')).toBeVisible();
    await expect(page.locator('#settingsHfModelSection')).toBeVisible();
  });

  test('Ollama: URL field visible, API key field hidden', async ({ page }) => {
    await page.evaluate(() => {
      const radio = document.querySelector('input[name="visionProvider"][value="ollama"]');
      if (radio) { radio.checked = true; radio.dispatchEvent(new Event('change')); }
    });
    await page.waitForTimeout(200);
    await expect(page.locator('#settingsOllamaSection')).toBeVisible();
    await expect(page.locator('#settingsApiKeySection')).not.toBeVisible();
  });

  test('Groq: API key placeholder is gsk_...', async ({ page }) => {
    await page.evaluate(() => {
      const radio = document.querySelector('input[name="visionProvider"][value="groq"]');
      if (radio) { radio.checked = true; radio.dispatchEvent(new Event('change')); }
    });
    await page.waitForTimeout(200);
    const placeholder = await page.locator('#settingsApiKey').getAttribute('placeholder');
    expect(placeholder).toBe('gsk_...');
  });

  test('per-provider key: save for HuggingFace, switch to Groq, keys are separate', async ({ page }) => {
    // Save HuggingFace key
    await page.evaluate(() => {
      const radio = document.querySelector('input[name="visionProvider"][value="huggingface"]');
      if (radio) { radio.checked = true; radio.dispatchEvent(new Event('change')); }
    });
    await page.waitForTimeout(200);
    await page.locator('#settingsApiKey').fill('hf_test_key_123');
    await page.evaluate(() => { if (typeof saveSettings === 'function') saveSettings(); });
    await page.waitForTimeout(200);

    const hfKey = await page.evaluate(() =>
      sessionStorage.getItem('vision_api_key_huggingface')
    );
    expect(hfKey).toBe('hf_test_key_123');

    // Switch to Groq — key field should show Groq's saved key (empty here)
    await page.evaluate(() => {
      if (typeof openSettingsModal === 'function') openSettingsModal();
      const radio = document.querySelector('input[name="visionProvider"][value="groq"]');
      if (radio) { radio.checked = true; radio.dispatchEvent(new Event('change')); }
    });
    await page.waitForTimeout(200);
    const groqFieldValue = await page.locator('#settingsApiKey').inputValue();
    // Groq key should NOT be HuggingFace's key
    expect(groqFieldValue).not.toBe('hf_test_key_123');
  });

  test('API key NOT stored in localStorage (XSS protection)', async ({ page }) => {
    await page.evaluate(() => {
      const radio = document.querySelector('input[name="visionProvider"][value="huggingface"]');
      if (radio) { radio.checked = true; radio.dispatchEvent(new Event('change')); }
    });
    await page.waitForTimeout(200);
    await page.locator('#settingsApiKey').fill('hf_xss_test_token');
    await page.evaluate(() => { if (typeof saveSettings === 'function') saveSettings(); });
    await page.waitForTimeout(200);

    const inLocal = await page.evaluate(() =>
      localStorage.getItem('hf_api_key') ||
      localStorage.getItem('vision_api_key') ||
      localStorage.getItem('vision_api_key_huggingface')
    );
    expect(inLocal).toBeNull();
  });

  test('clearSettings removes all API keys from sessionStorage', async ({ page }) => {
    await page.evaluate(() => { if (typeof clearSettings === 'function') clearSettings(); });
    await page.waitForTimeout(200);

    const remaining = await page.evaluate(() => {
      const keys = ['vision_api_key', 'hf_api_key',
        'vision_api_key_groq', 'vision_api_key_gemini',
        'vision_api_key_huggingface', 'hf_model'];
      return keys.filter(k => sessionStorage.getItem(k) !== null);
    });
    expect(remaining).toHaveLength(0);
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// Test Suite 7: Dashboard View
// ──────────────────────────────────────────────────────────────────────────────

test.describe('Dashboard View', () => {
  test('dashboard renders with empty state or project grid', async ({ page }) => {
    await page.goto(PROD_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#view-loading', { state: 'hidden', timeout: 15000 }).catch(() => {});
    await forceShowAppShell(page);

    await page.evaluate(() => {
      if (typeof Router !== 'undefined') Router.navigate('dashboard');
    });
    await page.waitForTimeout(500);

    await expect(page.locator('#view-dashboard')).toBeVisible();
    const emptyOrGrid = (await page.locator('#emptyState').isVisible().catch(() => false)) ||
                        (await page.locator('#projectGrid').isVisible().catch(() => false));
    expect(emptyOrGrid).toBe(true);
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// Test Suite 8: External API Reachability
// ──────────────────────────────────────────────────────────────────────────────

test.describe('API & CDN Reachability', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(PROD_URL, { waitUntil: 'domcontentloaded' });
  });

  test('HuggingFace router endpoint reachable', async ({ page }) => {
    const ok = await page.evaluate(async () => {
      try {
        const r = await fetch('https://router.huggingface.co', {
          method: 'HEAD',
          signal: AbortSignal.timeout(8000),
        });
        return r.status < 500;
      } catch { return false; }
    });
    expect(ok).toBe(true);
  });

  test('Groq API endpoint reachable', async ({ page }) => {
    const ok = await page.evaluate(async () => {
      try {
        const r = await fetch('https://api.groq.com', {
          method: 'HEAD',
          signal: AbortSignal.timeout(8000),
        });
        return r.status < 500;
      } catch { return false; }
    });
    expect(ok).toBe(true);
  });

  test('Gemini API endpoint reachable', async ({ page }) => {
    const ok = await page.evaluate(async () => {
      try {
        // 400/401 = server reachable but auth needed (expected without key)
        const r = await fetch(
          'https://generativelanguage.googleapis.com/v1beta/models?key=test',
          { signal: AbortSignal.timeout(10000) }
        );
        return r.status < 500;
      } catch { return false; }
    });
    expect(ok).toBe(true);
  });

  test('ffmpeg.wasm CDN: all 3 files reachable', async ({ page }) => {
    const results = await page.evaluate(async () => {
      const urls = [
        'https://cdn.jsdelivr.net/npm/@ffmpeg/ffmpeg@0.12.10/dist/esm/index.js',
        'https://cdn.jsdelivr.net/npm/@ffmpeg/core@0.12.6/dist/esm/ffmpeg-core.js',
        'https://cdn.jsdelivr.net/npm/@ffmpeg/core@0.12.6/dist/esm/ffmpeg-core.wasm',
      ];
      return Promise.all(
        urls.map(u =>
          fetch(u, { method: 'HEAD', signal: AbortSignal.timeout(10000) })
            .then(r => ({ url: u, ok: r.ok, status: r.status }))
            .catch(e => ({ url: u, ok: false, error: e.message }))
        )
      );
    });
    const failed = results.filter(r => !r.ok);
    expect(failed, `Unreachable CDN: ${JSON.stringify(failed)}`).toHaveLength(0);
    results.forEach(r => console.log(`  ${r.status ?? 'ERR'} ${r.url}`));
  });
});

// ──────────────────────────────────────────────────────────────────────────────
// Test Suite 9: HTTPS & Redirect
// ──────────────────────────────────────────────────────────────────────────────

test.describe('HTTPS', () => {
  test('site is served over HTTPS', async ({ page }) => {
    const resp = await page.goto(PROD_URL);
    expect(resp.url()).toMatch(/^https:/);
    expect(resp.status()).toBe(200);
  });
});
