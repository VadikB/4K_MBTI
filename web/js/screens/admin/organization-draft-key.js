const ASSESSMENT_DRAFT_ACTIONS = new Set([
  'preview-early-data',
  'preview-questionnaire',
  'questionnaire-preview',
]);

export const createAdminOrganizationDraftKey = ({
  identityKey,
  organizationId,
  action,
  assessmentRef = '',
  revisionId = '',
}) => {
  const normalizedAction = String(action || 'unknown');
  const scope = ASSESSMENT_DRAFT_ACTIONS.has(normalizedAction)
    ? String(assessmentRef || '').trim()
    : 'organization';
  const revision = normalizedAction === 'questionnaire-preview'
    ? ':' + String(revisionId || '').trim()
    : '';
  return String(identityKey || '') + ':' + Number(organizationId) + ':' + normalizedAction + ':' + scope + revision;
};
