// Technical projection of server state; question text/definitions come from artifacts through API.
export const resumeOnboardingIndex = (model, onboarding = {}) => {
  const saved = model?.state || {};
  if (!saved.consent_accepted_at || saved.consent_version !== model?.readiness?.briefing?.consent_version) {
    return Number(onboarding.current_step || saved.current_step || 0) > 0 ? 1 : 0;
  }
  const questions = model?.readiness?.briefing?.questions || [];
  const missing = questions.findIndex((_question, index) => !String(saved.answers_json?.[`answer_${index + 1}`] || '').trim());
  if (missing >= 0) return 2 + missing;
  if (!model?.mandatory_complete) return 2 + questions.length;
  const explanations = 3 + questions.length;
  if (['completed', 'skipped'].includes(onboarding.status)) return explanations + 2;
  return Math.max(explanations, Math.min(explanations + 2, Number(onboarding.current_step || 0)));
};

export const onboardingScopeKey = (userId, model) => [
  userId, model?.readiness?.organization_id, model?.readiness?.assignment_ref,
  model?.readiness?.questionnaire_revision_id,
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
  const plan = snapshot?.plan || snapshot;
  if (snapshot?.cycle_id && Array.isArray(plan?.route) && plan.route.length > 0
      && Number(plan.time_budget_seconds) > 0 && Number(plan.calendar_window_seconds) > 0) return 'ready';
  if (model?.preparation_operation?.status === 'completed') return 'plan_missing';
  return 'preparing';
};
