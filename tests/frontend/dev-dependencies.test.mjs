import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';

const require = createRequire(import.meta.url);
// Exercise the installed transitive matcher, without adding an application import.
const matcherPath = path.resolve('node_modules/picomatch');
const picomatch = require(matcherPath);

test('dev matcher preserves project glob matching, scanning and POSIX punctuation', () => {
  const matches = picomatch('web/js/**/*.js');
  assert.equal(matches('web/js/main.js'), true);
  assert.equal(matches('web/js/utils/report-comparison.js'), true);
  assert.equal(matches('web/styles/report.css'), false);
  assert.equal(matches('web/js/.hidden.js'), false);
  assert.equal(picomatch('web/js/**/*.js', { dot: true })('web/js/.hidden.js'), true);
  assert.equal(picomatch.scan('web/js/**/*.js').base, 'web/js');
  assert.equal(picomatch.isMatch('a.js', ['*.js', '*.mjs']), true);
  assert.equal(picomatch.isMatch('\\', '[[:punct:]]'), true);
  assert.equal(picomatch.isMatch('a', '[[:punct:]]'), false);
});

test('dev matcher completes CVE-2026-112366 attack cases in a bounded subprocess', () => {
  const script = `
    const assert = require('node:assert/strict');
    const pm = require(${JSON.stringify(require.resolve(matcherPath))});
    const cases = [
      ['+(*a)', 'a'.repeat(80) + '!'], ['*(*a)', 'a'.repeat(80) + '!'],
      ['+(a*)', 'a'.repeat(80) + '/'], ['*(a*)', 'a'.repeat(80) + '/'],
      ['+(*)', 'a'.repeat(80) + '/'], ['*(*)', 'a'.repeat(80) + '/'],
      ['+(*)b', 'a'.repeat(80) + '!'], ['*(*)b', 'a'.repeat(80) + '!'],
      ['+(*a)c', 'a'.repeat(80) + '!'], ['+(a*b)', 'ab'.repeat(40) + '!'],
      ['+(**)', 'a'.repeat(80) + '/.'], ['+(**a)', 'a'.repeat(80) + '!'],
      ['+(@(*a))', 'a'.repeat(80) + '!'], ['+(?(*a))', 'a'.repeat(80) + '!']
    ];
    for (const options of [{}, { windows: true }, { capture: true }]) {
      for (const [pattern, input] of cases) assert.equal(pm.isMatch(input, pattern, options), false, pattern);
    }
  `;
  const result = spawnSync(process.execPath, ['-e', script], { timeout: 5000, encoding: 'utf8' });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stderr);
});

test('Knip still detects unused files, exports and declared dependencies', async (t) => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'p4k-knip-compat-'));
  t.after(() => fs.rm(root, { recursive: true, force: true }));
  await fs.mkdir(path.join(root, 'src'));
  await fs.writeFile(path.join(root, 'package.json'), JSON.stringify({
    name: 'p4k-knip-sentinel', private: true, type: 'module',
    dependencies: { 'p4k-unused-sentinel-dependency': '1.0.0' },
  }));
  await fs.writeFile(path.join(root, 'knip.json'), JSON.stringify({
    entry: ['src/main.js'], project: ['src/**/*.js'], ignoreExportsUsedInFile: true,
  }));
  await fs.writeFile(path.join(root, 'src/main.js'), "import { used } from './used.js'; console.log(used());\n");
  await fs.writeFile(path.join(root, 'src/used.js'), 'export const used = () => 42; export const unusedExport = () => 13;\n');
  await fs.writeFile(path.join(root, 'src/unused.js'), 'export const unusedFile = true;\n');
  const cli = path.resolve('node_modules/knip/bin/knip.js');
  const result = spawnSync(process.execPath, [cli, '--reporter', 'json'], {
    cwd: root, timeout: 10000, encoding: 'utf8', env: { ...process.env, CI: 'true' },
  });
  assert.ifError(result.error);
  assert.equal(result.status, 1, result.stderr);
  const { issues } = JSON.parse(result.stdout);
  assert.ok(issues.some((row) => row.file === 'src/unused.js' && row.files.length));
  assert.ok(issues.some((row) => row.file === 'src/used.js' && row.exports.some((item) => item.name === 'unusedExport')));
  assert.ok(issues.some((row) => row.file === 'package.json' && row.dependencies.some((item) => item.name === 'p4k-unused-sentinel-dependency')));
});
