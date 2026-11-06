// Generate an immutable local delivery inventory AFTER all checks and docs.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
const root = process.cwd();
const evidence = 'docs/evc/evidence/path-auth-fix';
const sha = async (name) => crypto.createHash('sha256').update(await fs.readFile(path.join(root, name))).digest('hex');
async function walk(directory) {
  const names = [];
  for (const entry of await fs.readdir(directory, { withFileTypes: true })) {
    const name = path.join(directory, entry.name);
    if (entry.isDirectory()) names.push(...await walk(name));
    else names.push(path.relative(root, name));
  }
  return names;
}
const write = (name, body) => fs.writeFile(path.join(root, evidence, name), JSON.stringify(body, null, 2) + '\n');
const runtimeSources = ['web/js/screen-loaders.js', 'web/js/screens/chat.js', 'web/js/session.js'];
const code = [...await walk(path.join(root, 'web/js')), ...await walk(path.join(root, 'web/dist')),
  ...await walk(path.join(root, 'tests/frontend')), 'tests/browser/auth-r03.spec.mjs',
  'tests/browser/auth-recovery.spec.mjs', 'playwright.config.mjs', 'package.json', 'package-lock.json',
  'web/index.html', 'tests/e2e/test_email_admission_http.py', 'tests/e2e/test_adm28_static_http.py'];
const hashes = Object.fromEntries(await Promise.all(code.sort().map(async (name) => [name, await sha(name)])));
await write('code-identity.json', {
  base: 'dea8c44a183c2ac5f4b527e53cdeed0a39bcf454', branch: 'codex/path-final-audit',
  main_test_last_verified: '946a46cb71e5ca5cc99778f036807d6c193188dc',
  version: '2.0.68', runtime_sources_changed: runtimeSources, files: hashes,
  deployment: 'UNCHANGED_LAST_VERIFIED_946a46c', new_ci: 'NOT_RUN_NO_PR_AUTHORIZED',
  historical_auth_causality: 'NOT_ESTABLISHED', prep_diag_01_root_cause: 'UNKNOWN',
  external_actions: Object.fromEntries(['paid_llm', 'working_database', 'version_bump', 'branch_push',
    'pr', 'merge', 'deploy', 'program_activation', 'artifact_publish'].map((name) => [name, false])),
});
const files = [...new Set([...code, ...await walk(path.join(root, evidence)),
  'docs/evc/tasks/path-auth-fix.md', 'docs/evc/tasks/pilot-program-release/STATE.md',
  'docs/evc/reports/path-auth-fix.md'])].filter((name) => name !== `${evidence}/FILES.json`).sort();
await write('FILES.json', Object.fromEntries(await Promise.all(files.map(async (name) => [name, await sha(name)]))));
process.stdout.write(JSON.stringify({ files: files.length, code_files: code.length, dist_files: code.filter((name) => name.startsWith('web/dist/')).length }) + '\n');
