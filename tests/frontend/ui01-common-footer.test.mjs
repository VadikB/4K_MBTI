import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

import {
  shouldShowAppFooter,
  shouldShowEntryHeader,
  shouldShowFooterRelease,
} from '../../web/js/components/app-footer.js';

const html = await readFile(new URL('../../web/index.html', import.meta.url), 'utf8');
const baseCss = await readFile(new URL('../../web/styles/base.css', import.meta.url), 'utf8');
const componentsCss = await readFile(new URL('../../web/styles/components.css', import.meta.url), 'utf8');
const main = await readFile(new URL('../../web/js/main.js', import.meta.url), 'utf8');

test('shared footer is visible on common panels and hidden on chat panels', () => {
  assert.equal(shouldShowAppFooter('auth-panel'), true);
  assert.equal(shouldShowAppFooter('dashboard-panel'), true);
  assert.equal(shouldShowAppFooter('report-panel'), true);
  assert.equal(shouldShowAppFooter('admin-panel'), true);
  assert.equal(shouldShowAppFooter('chat-panel'), false);
  assert.equal(shouldShowAppFooter('interview-panel'), false);
  assert.equal(shouldShowAppFooter('onboarding-panel'), false);
  assert.equal(shouldShowAppFooter(undefined), false);
  assert.equal(shouldShowEntryHeader('session-restore-panel'), true);
  assert.equal(shouldShowEntryHeader('auth-panel'), true);
  assert.equal(shouldShowEntryHeader('auth-complete-panel'), true);
  assert.equal(shouldShowEntryHeader('dashboard-panel'), false);
  assert.equal(shouldShowFooterRelease('auth-panel'), false);
  assert.equal(shouldShowFooterRelease('dashboard-panel'), true);
  assert.match(main, /initAppFooter\(\)/);
});

test('footer has one non-interactive document block and a runtime year', () => {
  assert.equal((html.match(/<footer class="app-footer"/g) || []).length, 1);
  assert.match(html, />Политика конфиденциальности<\/span>/);
  assert.match(html, />Согласие на обработку персональных данных<\/span>/);
  assert.match(html, /© <span data-app-footer-year><\/span> LIDUM/);
  assert.doesNotMatch(html, /href="#"[^>]*>\s*(?:Политика|Согласие)/);
});

test('footer uses shared Onest and palette tokens with responsive flow layout', () => {
  assert.match(baseCss, /\.shell \{[\s\S]*flex-direction: column/);
  assert.match(componentsCss, /\.app-footer \{[\s\S]*font-family: "Onest", sans-serif/);
  assert.match(componentsCss, /color: var\(--palette-graphite-600\)/);
  assert.match(componentsCss, /\.app-footer-documents \{[\s\S]*gap: 32px[\s\S]*font-size: 12px[\s\S]*line-height: 16px[\s\S]*letter-spacing: 0.8px/);
  assert.match(componentsCss, /@media \(max-width: 479px\)[\s\S]*padding-right: max\(16px[\s\S]*flex-direction: column[\s\S]*gap: 12px/);
  assert.doesNotMatch(componentsCss, /position:\s*fixed/);
});
