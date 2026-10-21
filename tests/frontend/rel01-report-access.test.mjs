import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

const organizations = fs.readFileSync('web/js/screens/admin/organizations.js', 'utf8');
const reports = fs.readFileSync('web/js/screens/admin/reports.js', 'utf8');
const report = fs.readFileSync('web/js/screens/report.js', 'utf8');
const wiring = fs.readFileSync('web/js/wiring.js', 'utf8');
const main = fs.readFileSync('web/js/main.js', 'utf8');

test('REL01 keeps participant mandatory and selects concrete organization admins', () => {
  assert.match(organizations, /Участник — обязательный получатель/);
  assert.match(organizations, /questionnaire_recipient_user/);
  assert.match(organizations, /recipient_user_ids/);
  assert.match(wiring, /recipientUserIds/);
});

test('UX-FIX20-03 routes invitations through the shared selected assessment', () => {
  assert.match(organizations, /getSelectedAdminOrganizationAssessment/);
  assert.doesNotMatch(wiring, /sendAdminOrganizationMemberInvitation\([\s\S]{0,160}querySelector\('input\[name="assignment_ref"\]'/);
  assert.match(wiring, /sendAdminOrganizationMemberInvitation\([\s\S]{0,160}getSelectedAdminOrganizationAssessment/);
});

test('REL01 customer report uses protected read and PDF endpoints', () => {
  assert.match(reports, /\/users\/admin\/m8-access\/reports/);
  assert.match(reports, /customerAccess: true/);
  assert.match(report, /admin\/m8-access\/reports/);
  assert.match(wiring, /m8ReportAccess === 'customer'/);
  assert.match(report, /report_access.*customer/);
  assert.match(main, /report_access.*customer/);
});
