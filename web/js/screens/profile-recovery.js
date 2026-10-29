import { readApiResponse, fetchWithDeadline as fetch } from '../api.js';
import { state, persistAssessmentContext } from '../state.js';
import { hasRequiredProfileFields, shouldOfferNoChangesQuickReply } from '../utils/format.js';

export const shouldRecoverProfileOnAssessmentError = (message) => {
  const normalized = String(message || '').toLowerCase();
  return ['m4_profile_not_ready', 'm4_profile_scope_mismatch', 'm4_profile_selection_required'].some((code) => normalized.includes(code)) || normalized.includes('для пользователя не определена роль') || normalized.includes('завершите настройку профиля');
};

export const recoverProfileCompletionForAssessment = async ({ resumeAssessment = true } = {}) => {
  const journeyResponse = await fetch('/users/' + state.pendingUser.id + '/journey-state', { credentials: 'same-origin' });
  const journey = await readApiResponse(journeyResponse, 'Не удалось восстановить актуальный этап оценки.');
  if (journey.next_action === 'show_onboarding') {
    const { openOnboarding } = await import('./onboarding.js');
    await openOnboarding({ currentStep: Number(journey.onboarding?.current_step || 0) });
    return;
  }
  if (journey.next_action === 'wait_for_acquaintance_data') {
    const { openAcquaintanceWaiting } = await import('../router.js');
    openAcquaintanceWaiting(journey.acquaintance?.readiness);
    return;
  }
  if (journey.next_action !== 'complete_profile') throw new Error('Откройте текущую оценку через личный кабинет.');
  const response = await fetch('/users/session/reopen-profile', {
    method: 'POST',
    credentials: 'same-origin',
  });
  const data = await readApiResponse(response, 'Не удалось вернуть пользователя к настройке профиля.');
  const agent = data?.agent;
  if (!agent?.session_id) {
    throw new Error('Не удалось открыть сценарий настройки профиля.');
  }

  state.sessionId = agent.session_id;
  state.completed = false;
  state.isChatSubmitting = false;
  state.isNewUserFlow = false;
  state.isAdmin = false;
  state.pendingUser = data.user || agent.user || state.pendingUser;
  state.pendingAgentMessage = agent.message || 'Продолжим настройку профиля.';
  state.pendingRoleOptions = Array.isArray(agent.role_options) ? agent.role_options : [];
  state.pendingActionOptions = Array.isArray(agent.action_options) ? agent.action_options : [];
  state.pendingConsentTitle = agent.consent_title || null;
  state.pendingConsentText = agent.consent_text || null;
  state.pendingNoChangesQuickReply = shouldOfferNoChangesQuickReply(state.pendingAgentMessage) && hasRequiredProfileFields(state.pendingUser);
  state.preparedAssessmentStartResponse = null;
  state.resumeAssessmentAfterProfileCompletion = resumeAssessment;
  persistAssessmentContext();

  const chatModule = await import('./chat.js');
  chatModule.openChat();
};
