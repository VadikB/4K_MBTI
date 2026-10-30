import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const source = readFileSync(new URL('../../web/js/screens/admin/organizations.js', import.meta.url), 'utf8');
const wiring = readFileSync(new URL('../../web/js/wiring.js', import.meta.url), 'utf8');

test('ARCH30 connects an exact published program version from the superadmin UI', () => {
  assert.match(source, /assessment_programs/);
  assert.match(source, /program_definition_id/);
  assert.match(source, /createOperationId\(\)/);
  assert.match(source, /\/assessment-program/);
  assert.match(wiring, /connect-assessment-program/);
  assert.match(wiring, /connectAdminOrganizationProgram/);
});
