import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const tokens = await readFile('web/styles/tokens.css', 'utf8');
const report = await readFile('web/js/screens/report.js', 'utf8');
const styles = await readFile('web/styles/screens/report.css', 'utf8');

test('UI02 maps waiting statuses to the exact owner palette pair', () => {
  assert.match(tokens, /--status-wait-bg:\s*var\(--palette-coral-050\)/);
  assert.match(tokens, /--status-wait-text:\s*var\(--palette-coral-500\)/);
  assert.match(tokens, /--palette-coral-050:\s*#ffe5e0/i);
  assert.match(tokens, /--palette-coral-500:\s*#ff563d/i);
});

test('UI02 measures real radar labels and keeps them inside a safe area', () => {
  assert.match(report, /document\.fonts\?\.ready/);
  assert.match(report, /label\.getBBox\(\)/);
  assert.match(report, /const safeInset = 24/);
  assert.match(report, /const scheduleM8RadarLabelFit = \(node\) => \{\s*fitM8RadarLabels\(node\)/);
  assert.match(report, /splitRadarLabel/);
  assert.match(report, /<tspan/);
  assert.match(report, /data-m8-skill-id/);
  assert.match(styles, /\.m8-report-chart\s*\{[\s\S]*padding:\s*var\(--space-3\)/);
  assert.match(styles, /\.m8-radar-label[\s\S]*pointer-events:\s*auto/);
});

test('UI02 preserves readable overview access on narrow screens', () => {
  assert.match(styles, /\.m8-report-chart\.is-overview svg\s*\{[\s\S]*min-width:\s*680px/);
  assert.match(styles, /\.m8-report-chart\.is-overview\s*\{[\s\S]*overflow-x:\s*auto/);
});
