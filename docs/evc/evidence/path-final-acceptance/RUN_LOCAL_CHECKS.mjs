// Оператор этой карточки: только бесплатные локальные проверки, не runtime runner.
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { gzipSync } from 'node:zlib';

const root = path.resolve(import.meta.dirname, '../../../..');
const toolsRoot = path.resolve(process.argv[2] || root);
const python = process.argv[3] || path.join(toolsRoot, '.venv/bin/python');
const digest = (filename) => createHash('sha256').update(readFileSync(filename)).digest('hex');
const distHashes = () => Object.fromEntries(readdirSync(path.join(root, 'web/dist')).sort()
  .map((name) => [name, digest(path.join(root, 'web/dist', name))]));
const environment = {
  PATH: `${toolsRoot}/node_modules/.bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin`,
  LANG: 'en_US.UTF-8', PYTHONPATH: root, PYTHONDONTWRITEBYTECODE: '1',
  AGENT4K_ISOLATED_STAND: '1', AGENT4K_STAND_MARKER: 'stand-10.2:offline-acceptance',
  DB_HOST: '127.0.0.1', DB_PORT: '9', DB_NAME: 'product4k_pytest_ac_a7d7a9d',
  DB_USER: 'synthetic', DB_POOL_MIN_SIZE: '0', LOG_TO_FILE: 'false', AUDIT_LOGS_TO_DB: 'false',
};
const frontendFiles = readdirSync(path.join(root, 'tests/frontend')).sort()
  .filter((name) => name.endsWith('.test.mjs')).map((name) => `tests/frontend/${name}`);
const commands = [
  ['lint', ['npm', 'run', 'lint:js']],
  ['frontend', ['node', '--test', ...frontendFiles]],
  ['http-and-source', [python, '-m', 'pytest', '-q', '-m', 'not integration and not llm',
    'tests/e2e/test_adm27_assignment_http.py', 'tests/e2e/test_m3_role_profile_selection_http.py',
    'tests/unit/test_m3_base_roles.py']],
  ['build', ['npm', 'run', 'build:web']],
  ['diff', ['git', 'diff', '--check']],
];
const distBefore = distHashes();
const checkedPaths = ['web/js/screens/admin/organizations.js', 'tests/browser/auth-r03.spec.mjs',
  'Api/assessment_programs.py', 'assessment_definitions/role_profiles/competencies_4k/1.1/base_roles.json',
  'assessment_definitions/role_profiles/competencies_4k/1.1/manifest.json'];
const checkedHashes = Object.fromEntries(checkedPaths.map((file) => [file, digest(path.join(root, file))]));
const results = [];
for (const [name, command] of commands) {
  const start = new Date().toISOString();
  const result = spawnSync(command[0], command.slice(1), {
    cwd: root, env: environment, encoding: 'utf8', timeout: 120000, maxBuffer: 8 * 1024 * 1024,
  });
  const output = `${result.stdout || ''}${result.stderr || ''}`;
  const outputName = `${name}.txt.gz`;
  writeFileSync(path.join(import.meta.dirname, outputName), gzipSync(Buffer.from(output)));
  results.push({ name, command, start, exit_code: result.status, signal: result.signal,
    error: result.error?.message || null, output: outputName, sha256: digest(path.join(import.meta.dirname, outputName)) });
}
const distAfter = distHashes();
const unchanged = spawnSync('git', ['diff', '--name-only', 'a7d7a9d5522cd96aae92369fc68aaff1e9fa60c7',
  '--', 'Api', 'scripts', 'assessment_definitions'], { cwd: root, env: environment, encoding: 'utf8' });
const ok = results.every((item) => item.exit_code === 0 && !item.signal && !item.error)
  && unchanged.status === 0 && unchanged.stdout.trim() === ''
  && JSON.stringify(distBefore) === JSON.stringify(distAfter);
const report = { result: ok ? 'PASS_LOCAL_CHECKS' : 'FAIL', checked_hashes: checkedHashes,
  environment, results, dist_before: distBefore, dist_after: distAfter,
  build_idempotent: JSON.stringify(distBefore) === JSON.stringify(distAfter),
  unchanged_backend_sources: unchanged.status === 0 && unchanged.stdout.trim() === '',
  working_database_used: false, llm_calls: 0, new_ci: false, merge: false, deploy: false };
writeFileSync(path.join(import.meta.dirname, 'local-checks.json'), JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({ result: report.result, checks: results.map(({ name, exit_code }) => ({ name, exit_code })),
  build_idempotent: report.build_idempotent, unchanged_backend_sources: report.unchanged_backend_sources }));
process.exitCode = ok ? 0 : 1;
