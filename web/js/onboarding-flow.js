// Technical projection of server state; question text/definitions come from artifacts through API.
export const resumeOnboardingIndex = (model, onboarding = {}) => {
  const saved = model?.state || {};
  const questions = model?.readiness?.briefing?.questions || [];
  // A committed prepared plan is stronger evidence than a stale questionnaire/consent
  // projection returned during reload. Never send a prepared participant back to step 1.
  if (model?.mandatory_complete && preparationView(model) === 'ready') return 5 + questions.length;
  if (!saved.consent_accepted_at || saved.consent_version !== model?.readiness?.briefing?.consent_version) {
    return Number(onboarding.current_step || saved.current_step || 0) > 0 ? 1 : 0;
  }
  const missing = questions.findIndex((_question, index) => !String(saved.answers_json?.[`answer_${index + 1}`] || '').trim());
  if (missing >= 0) return 2 + missing;
  if (!model?.mandatory_complete) return 2 + questions.length;
  const explanations = 3 + questions.length;
  if (['completed', 'skipped'].includes(onboarding.status)) return explanations + 2;
  return Math.max(explanations, Math.min(explanations + 2, Number(onboarding.current_step || 0)));
};

export const onboardingScopeKey = (userId, model) => [
  userId, model?.readiness?.organization_id, model?.readiness?.assignment_ref,
  model?.readiness?.questionnaire_revision_id, model?.assignment_id,
].map((value) => encodeURIComponent(String(value ?? ''))).join(':');

export const preparationView = (model, localError = null) => {
  if (localError?.kind === 'access') return 'access';
  if (localError?.kind === 'network') return 'network';
  if (localError?.kind === 'conflict') return 'conflict';
  if (localError?.kind === 'service') return 'service';
  if (model?.late_readiness?.status !== 'ready_to_prepare') return 'organization';
  if (model?.preparation_operation?.status === 'failed') return 'failed';
  if (['queued', 'running', 'unknown'].includes(model?.preparation_operation?.status)) return 'preparing';
  const snapshot = model?.prepared_plan;
  const admission = snapshot?.start_readiness;
  if (snapshot?.cycle_id && admission?.contract === 'm7_start_readiness/1'
      && admission.cycle_id === snapshot.cycle_id && admission.can_start === true
      && admission.plan_revision_id === snapshot.revision_id
      && Array.isArray(admission.reasons) && admission.reasons.length === 0) return 'ready';
  if (snapshot?.cycle_id) return 'plan_blocked';
  if (model?.preparation_operation?.status === 'completed') return 'plan_missing';
  return 'preparing';
};
