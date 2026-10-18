import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import test from 'node:test';

const tokens = readFileSync('web/styles/tokens.css', 'utf8').toLowerCase();
const components = readFileSync('web/styles/components.css', 'utf8').toLowerCase();
const markup = readFileSync('web/index.html', 'utf8').toLowerCase();
const allowedHex = new Set([
  '#222c30', '#68777c', '#d6e2e5', '#f7f9fb',
  '#ff563d', '#ff9d8e', '#ffc2b8', '#ffe5e0',
  '#18b8c6', '#83dce3', '#b3ebef', '#d9f6f8',
  '#f6f9f9', '#ffffff', '#b42318',
]);

const cssFiles = [
  ...readdirSync('web/styles', { withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith('.css'))
    .map((entry) => `web/styles/${entry.name}`),
  ...readdirSync('web/styles/screens', { withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith('.css'))
    .map((entry) => `web/styles/screens/${entry.name}`),
];

const collectFiles = (directory, extension) => readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
  const path = `${directory}/${entry.name}`;
  if (entry.isDirectory()) return collectFiles(path, extension);
  return entry.name.endsWith(extension) ? [path] : [];
});

test('UI03 exposes the owner palette and semantic aliases from one token source', () => {
  for (const color of [
    '#222c30', '#68777c', '#d6e2e5', '#f7f9fb',
    '#ff563d', '#ff9d8e', '#ffc2b8', '#ffe5e0',
    '#18b8c6', '#83dce3', '#b3ebef', '#d9f6f8',
    '#f6f9f9', '#ffffff', '#b42318',
  ]) assert.match(tokens, new RegExp(color));
  assert.match(tokens, /--bg-soft:\s*var\(--palette-canvas\)/);
  assert.match(tokens, /--success-soft:\s*var\(--palette-cyan-050\)/);
  assert.match(tokens, /--warning-surface:\s*var\(--palette-coral-050\)/);
  assert.match(tokens, /--danger:\s*var\(--palette-error\)/);
});

test('UI03 keeps participant and admin primary actions semantically distinct', () => {
  assert.match(components, /\.primary-button\s*\{[\s\S]*background:\s*var\(--accent-bright\);[\s\S]*color:\s*var\(--palette-graphite-900\)/);
  assert.match(components, /\.admin-panel \.primary-button,[\s\S]*background:\s*var\(--admin-primary\);[\s\S]*color:\s*var\(--admin-primary-text\)/);
});

test('UI03 prevents local six-digit hex colors outside the owner palette', () => {
  for (const file of [...cssFiles, ...collectFiles('web/js', '.js')]) {
    const colors = readFileSync(file, 'utf8').toLowerCase().match(/#[0-9a-f]{6}\b/g) ?? [];
    for (const color of colors) assert.ok(allowedHex.has(color), `${file}: ${color}`);
  }
});

test('UI03 keeps embedded SVG fills inside the owner palette', () => {
  for (const file of cssFiles) {
    const encodedColors = readFileSync(file, 'utf8').toLowerCase().match(/%23[0-9a-f]{6}\b/g) ?? [];
    for (const color of encodedColors) assert.ok(allowedHex.has(`#${color.slice(3)}`), `${file}: ${color}`);
  }
});

test('UI03 invalidates cached CSS and JavaScript entrypoints', () => {
  assert.match(markup, /styles\/screens\/auth\.css\?v=20261018-ui03-palette/);
  assert.match(markup, /web\/dist\/main\.js\?v=20261018-ui01-footer/);
});
