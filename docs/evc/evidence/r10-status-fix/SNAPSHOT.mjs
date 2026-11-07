// Immutable delivery snapshot, generated only after tests/docs are complete.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { execFileSync } from 'node:child_process';
const root = process.cwd();
const evidence = 'docs/evc/evidence/r10-status-fix';
const hash = async (name) => crypto.createHash('sha256').update(await fs.readFile(name)).digest('hex');
async function walk(directory) {
  const files = [];
  for (const entry of await fs.readdir(directory, { withFileTypes: true })) {
    const name = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await walk(name)); else files.push(name);
  }
  return files.sort();
}
const code = [...await walk('web/js'), ...await walk('web/dist'), ...await walk('tests/frontend'),
  'web/index.html', 'package.json', 'package-lock.json', 'playwright.config.mjs',
  ...['auth-r03.spec.mjs', 'auth-recovery.spec.mjs', 'program-connection-feedback.spec.mjs'].map((name) => `tests/browser/${name}`)];
const file = 'web/js/screens/admin/organizations.js';
const comparator = (source) => source.match(/const isExactProgramConnection = [\s\S]*?;/)?.[0];
const before = execFileSync('git', ['show', `4f2e884:${file}`], { encoding: 'utf8' });
const after = await fs.readFile(file, 'utf8');
const identity = {
  base: '4f2e884eac9e00f6f169dddfe5fad6d7a910aaa9', inherited_auth_fix: 'bf637af8e1ee89c1a8d5621c4ce694a52bb0806e',
  branch: 'codex/path-final-audit', version: '2.0.68', runtime_sources_changed: [file],
  main_test_last_verified: '946a46cb71e5ca5cc99778f036807d6c193188dc', new_ci: 'NOT_RUN_NO_PR_AUTHORIZED',
  exact_readback_comparator_unchanged: comparator(before) === comparator(after) && Boolean(comparator(before)),
  timeout_root_cause: 'UNKNOWN', historical_auth_causality: 'NOT_ESTABLISHED', prep_diag_01_root_cause: 'UNKNOWN',
  external_actions: Object.fromEntries(['paid_llm', 'working_database', 'version_bump', 'branch_push', 'pr',
    'merge', 'deploy', 'program_activation', 'artifact_publish'].map((name) => [name, false])),
  files: Object.fromEntries(await Promise.all(code.map(async (name) => [name, await hash(name)]))),
};
await fs.writeFile(`${evidence}/code-identity.json`, JSON.stringify(identity, null, 2) + '\n');
const files = [...new Set([...code, ...await walk(evidence), 'docs/evc/tasks/r10-status-fix.md',
  'docs/evc/reports/r10-status-fix.md', 'docs/evc/tasks/pilot-program-release/STATE.md'])]
  .filter((name) => name !== `${evidence}/FILES.json`).sort();
await fs.writeFile(`${evidence}/FILES.json`, JSON.stringify(Object.fromEntries(await Promise.all(
  files.map(async (name) => [name, await hash(name)]))), null, 2) + '\n');
process.stdout.write(JSON.stringify({ root, files: files.length, code_files: code.length, dist_files: code.filter((name) => name.startsWith('web/dist/')).length }) + '\n');
