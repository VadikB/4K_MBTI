// Mechanical offline byte inventory; not a product runtime or methodology artifact.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../../../..');
const selected = new Set();
const add = (relative) => {
  const full = path.resolve(root, relative);
  if (!full.startsWith(root + path.sep) || !fs.statSync(full).isFile()) throw new Error('INVENTORY_PATH:' + relative);
  selected.add(path.relative(root, full));
};
const walk = (directory) => {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    if (entry.name.startsWith('.') || entry.name === 'FILES.json') continue;
    const full = path.join(directory, entry.name);
    if (entry.isDirectory()) walk(full);
    else if (entry.isFile()) add(path.relative(root, full));
  }
};
walk(here);
const markdown = [
  'docs/evc/reports/path-final-audit-2068.md', 'docs/evc/tasks/path-final-audit.md',
  'docs/evc/tasks/path-auth-diagnostic.md', 'docs/evc/tasks/prep-diag-01-review.md',
  'docs/evc/evidence/path-final-audit/README.md',
];
let localLinks = 0;
for (const relative of markdown) {
  add(relative);
  const text = fs.readFileSync(path.join(root, relative), 'utf8');
  for (const match of text.matchAll(/\]\(([^)]+)\)/g)) {
    if (/^(https?:|#)/.test(match[1])) continue;
    const full = path.resolve(root, path.dirname(relative), match[1].split('#')[0]);
    if (!fs.existsSync(full)) throw new Error('BROKEN_LOCAL_LINK:' + relative + ':' + match[1]);
    if (fs.statSync(full).isFile()) add(path.relative(root, full));
    localLinks += 1;
  }
}
add('docs/evc/tasks/pilot-program-release/STATE.md');
const old = 'docs/evc/evidence/pilot-1.2-path/server-evidence';
add(old + '/MANIFEST.json');
for (const item of JSON.parse(fs.readFileSync(path.join(root, old, 'MANIFEST.json'))).files) add(path.join(old, item.path));
const identity = JSON.parse(fs.readFileSync(path.join(here, 'source-identities.json')));
for (const item of identity.files) add(item.path);
for (const name of ['PREP-DIAG-01.json', 'run.json', 'code-identity.json', 'final-failure-receipt.json',
  'cleanup.json', 'runner-result.json', 'preparation-blocker.png', 'export-regression/regression-result.json',
  'export-regression/export-before-cleanup.json', 'export-regression/export-receipt.json']) add('docs/evc/evidence/assessment-contour-2026-11-04/' + name);
for (const name of ['clean-before.json', 'after-selection.json', 'browser-full-first.json', 'browser-full-control.json',
  'auth-full-first-failure.png', 'ac02-integration.txt', 'container-owner.txt', 'owned-schemas-after-tests.txt', 'container-after-cleanup.txt']) add('docs/evc/evidence/path-ac02-ac05/' + name);
add('docs/evc/evidence/path-ac02-ac05-release-2068/browser.json');
for (const name of ['api.js', 'session.js', 'wiring.js', 'router.js', 'screen-loaders.js', 'main.js', 'config.js', 'screens/chat.js']) add('web/js/' + name);
add('web/index.html');
for (const name of fs.readdirSync(path.join(root, 'web/dist'))) add('web/dist/' + name);
for (const name of ['tests/browser/auth-recovery-race.diagnostic.mjs', 'tests/browser/auth-r03.spec.mjs',
  'tests/unit/test_path_final_audit_evidence.py', 'tests/unit/test_assessment_first_case.py',
  'tests/unit/test_m4_personalized_profile.py', 'tests/unit/test_m3_base_roles.py',
  'tests/e2e/test_adm27_assignment_http.py', 'tests/e2e/test_arch30_membership_http.py',
  'tests/e2e/test_m3_role_profile_selection_http.py', 'tests/e2e/test_path_start_readiness_http.py',
  'tests/integration/test_questionnaire_sources_db.py', 'tests/integration/test_path_start_assignment_lineage_db.py',
  'tests/integration/test_path_ac02_organization_create_db.py', 'tests/integration/test_profile_access_owned_stand.py',
  'tests/integration/test_m5_cycle_runtime_db.py', 'tests/integration/test_w02_acquaintance_db.py',
  'playwright.config.mjs', 'package.json', 'pyproject.toml']) add(name);
const linksPath = path.join(here, 'local-links.json');
fs.writeFileSync(linksPath, JSON.stringify({ result: 'PASS', local_links: localLinks, documents: markdown.length }, null, 2) + '\n');
add(path.relative(root, linksPath));
const files = [...selected].sort().map((relative) => {
  const body = fs.readFileSync(path.join(root, relative));
  return { path: relative, bytes: body.length, sha256: crypto.createHash('sha256').update(body).digest('hex') };
});
fs.writeFileSync(path.join(here, 'FILES.json'), JSON.stringify({ scope: 'Immutable audit snapshot; not product acceptance', files }, null, 2) + '\n');
process.stdout.write(JSON.stringify({ result: 'PASS_INVENTORY', files: files.length, local_links: localLinks }) + '\n');
