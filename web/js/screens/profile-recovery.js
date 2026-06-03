import { readApiResponse } from '../api.js';
import { state, persistAssessmentContext } from '../state.js';
import { shouldOfferNoChangesQuickReply } from '../utils/format.js';

export const shouldRecoverProfileOnAssessmentError = (message) => {
  const normalized = String(message || '').toLowerCase();
  return normalized.includes('для пользователя не определена роль') || normalized.includes('завершите настройку профиля');
};

export const recoverProfileCompletionForAssessment = async () => {
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
  state.pendingUser = data.user || agent.user || state.pendingUser;
  state.pendingAgentMessage = agent.message || 'Продолжим настройку профиля.';
  state.pendingRoleOptions = Array.isArray(agent.role_options) ? agent.role_options : [];
  state.pendingActionOptions = Array.isArray(agent.action_options) ? agent.action_options : [];
  state.pendingConsentTitle = agent.consent_title || null;
  state.pendingConsentText = agent.consent_text || null;
  state.pendingNoChangesQuickReply = shouldOfferNoChangesQuickReply(state.pendingAgentMessage);
  state.preparedAssessmentStartResponse = null;
  state.resumeAssessmentAfterProfileCompletion = true;
  persistAssessmentContext();

  const chatModule = await import('./chat.js');
  chatModule.openChat();
};
