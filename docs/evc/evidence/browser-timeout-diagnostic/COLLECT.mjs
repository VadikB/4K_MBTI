// Specific offline evidence inventory; no product methods/network/DB/provider.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { execFileSync } from 'node:child_process';
const root = process.cwd();
const directory = 'docs/evc/evidence/browser-timeout-diagnostic';
const old = 'docs/evc/evidence/path-auth-fix';
const read = async (name) => JSON.parse(await fs.readFile(name, 'utf8'));
const hash = async (name) => crypto.createHash('sha256').update(await fs.readFile(name)).digest('hex');
async function walk(directory) {
  const names = [];
  for (const entry of await fs.readdir(directory, { withFileTypes: true })) {
    const name = path.join(directory, entry.name);
    if (entry.isDirectory()) names.push(...await walk(name));
    else names.push(name);
  }
  return names.sort();
}
function specs(document) {
  const found = [];
  const visit = (suite) => { found.push(...suite.specs || []); (suite.suites || []).forEach(visit); };
  document.suites.forEach(visit);
  return found;
}
const failureActions = [];
for (const name of ['after/full-results.json', 'after/followup-results.json']) {
  const document = await read(`${old}/${name}`);
  for (const spec of specs(document)) for (const test of spec.tests) for (const run of test.results) {
    if (run.status === 'passed') continue;
    failureActions.push({ source: `${old}/${name}`, title: spec.title, status: run.status,
      duration_ms: run.duration, start_time: run.startTime,
      errors: (run.errors || []).map((error) => ({ location: error.location || null, message: error.message })) });
  }
}
const traces = [];
for (const group of ['current-targeted', 'comparison-targeted', 'current-full', 'comparison-status']) {
  for (const zip of (await walk(`${directory}/${group}`)).filter((name) => name.endsWith('trace.zip'))) {
    const parse = (name) => execFileSync('unzip', ['-p', zip, name], { maxBuffer: 20_000_000 })
      .toString().trim().split('\n').filter(Boolean).map(JSON.parse);
    const events = parse('1-trace.trace');
    const before = new Map(events.filter((event) => event.type === 'before').map((event) => [event.callId, event]));
    const actions = events.filter((event) => event.type === 'after').flatMap((event) => {
      const start = before.get(event.callId);
      if (!start || !['fill', 'click', 'selectOption', 'setViewportSize'].includes(start.method)) return [];
      return [{ method: start.method, selector: start.params?.selector || null,
        duration_ms: Number((event.endTime - start.startTime).toFixed(3)), error: event.error || null }];
    });
    const responses = parse('1-trace.network').filter((event) => event.type === 'resource-snapshot').flatMap((event) => {
      const snapshot = event.snapshot;
      const url = new URL(snapshot.request.url);
      return url.pathname.startsWith('/users/') ? [{ method: snapshot.request.method, path: url.pathname,
        status: snapshot.response.status, started: snapshot.startedDateTime, duration_ms: snapshot.time }] : [];
    });
    const testEvents = parse('test.trace');
    const testStarts = new Map(testEvents.filter((event) => event.type === 'before').map((event) => [event.callId, event]));
    const expectations = testEvents.filter((event) => event.type === 'after' && testStarts.get(event.callId)?.method === 'expect')
      .map((event) => { const start = testStarts.get(event.callId); return { title: start.title,
        location: start.stack?.[0] || null, start: start.startTime, end: event.endTime,
        failed: Boolean(event.error) }; });
    traces.push({ group, path: zip, sha256: await hash(zip), actions, responses, expectations });
  }
}
const sourcePaths = ['tests/browser/auth-r03.spec.mjs', 'playwright.config.mjs', 'web/js/main.js',
  'web/js/wiring.js', 'web/js/screens/admin/organizations.js'];
const fixedIdentity = await read(`${old}/code-identity.json`);
const currentTargeted = await read(`${directory}/current-targeted/results.json`);
const comparisonTargeted = await read(`${directory}/comparison-targeted/results.json`);
const currentFull = await read(`${directory}/current-full/results.json`);
const comparisonStatus = await read(`${directory}/comparison-status/results.json`);
const sourceIdentity = Object.fromEntries(await Promise.all(sourcePaths.map(async (name) => [name, {
  sha256: await hash(name), previous_fix_evidence_sha256: fixedIdentity.files[name] }])));
const diagnosis = {
  comparison_commit: 'dea8c44a183c2ac5f4b527e53cdeed0a39bcf454',
  product_commit: 'bf637af8e1ee89c1a8d5621c4ce694a52bb0806e',
  current_targeted: currentTargeted.stats,
  comparison_targeted: comparisonTargeted.stats,
  current_full: currentFull.stats,
  comparison_status_loss: comparisonStatus.stats,
  source_identity: sourceIdentity, historical_failure_actions: failureActions, traces,
  historical_timeout_root_cause: 'UNKNOWN', historical_auth_114_1_causality: 'NOT_ESTABLISHED',
  prep_diag_01_root_cause: 'UNKNOWN',
  reproduced_timeout: [currentTargeted, comparisonTargeted, currentFull].some((document) => specs(document)
    .some((spec) => spec.tests.some((test) => test.results.some((run) => run.status === 'timedOut')))),
  report_correction: 'Historical ADM full: click at757; followup: email fill at754, not the same action.',
  new_defect: { id: 'R10-STATUS-DIAG-01', cause: 'Final loadAdminOrganizations render removes DOM-only operation status',
    preexisting_before_auth_fix: true, admission_or_connection_lost: false,
    product_fix_performed: false, fix_authorized: false },
  product_changed_by_diagnosis: false, external_actions: false,
};
await fs.writeFile(`${directory}/diagnosis.json`, JSON.stringify(diagnosis, null, 2) + '\n');
const files = [...await walk(directory), ...sourcePaths,
  'docs/evc/tasks/browser-timeout-diagnostic.md', 'docs/evc/reports/browser-timeout-diagnostic.md',
  'docs/evc/tasks/r10-status-diag-01.md',
  'docs/evc/tasks/pilot-program-release/STATE.md', `${old}/code-identity.json`,
  `${old}/after/full-results.json`, `${old}/after/followup-results.json`]
  .filter((name) => name !== `${directory}/FILES.json`).sort();
await fs.writeFile(`${directory}/FILES.json`, JSON.stringify(Object.fromEntries(await Promise.all(
  files.map(async (name) => [name, await hash(name)]))), null, 2) + '\n');
process.stdout.write(JSON.stringify({ files: files.length, traces: traces.length, root }) + '\n');
