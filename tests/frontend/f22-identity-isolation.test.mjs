import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const organizations = await readFile('web/js/screens/admin/organizations.js', 'utf8');

test('F22-01 ignores a late member-import response after the authenticated identity changes', () => {
  assert.match(organizations, /const captureIdentityGuard = \(\) => \{[\s\S]*state\.identityEpoch[\s\S]*currentIdentityKey\(\)/);
  assert.match(organizations, /requestOrganizationsImport = async \(url, csvText, isCurrentIdentity\)/);
  assert.match(organizations, /readApiResponse\(response,[\s\S]*if \(!isCurrentIdentity\(\)\) return null;[\s\S]*state\.adminOrganizations =/);
  assert.match(organizations, /const isCurrentIdentity = captureIdentityGuard\(\);[\s\S]*if \(!result \|\| !isCurrentIdentity\(\)\) return;/);
  assert.match(organizations, /catch \(error\) \{[\s\S]*if \(!isCurrentIdentity\(\)\) return;[\s\S]*setStatus\(error\.message/);
});
