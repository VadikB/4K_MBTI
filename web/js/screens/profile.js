import { state, persistAssessmentContext, setCurrentScreen } from '../state.js';
import {
  profilePanel,
  profileName,
  profileRole,
  profileTotalAssessments,
  profileAverageScore,
  profileFullName,
  profileEmail,
  profilePhone,
  profileTelegram,
  profileJobDescription,
  profileCompanyIndustry,
} from '../dom.js';
import { sanitizeDisplayRole, sanitizeDisplayMetaText } from '../utils/format.js';
import { readApiResponse } from '../api.js';
import { hideAllPanels, syncUrlState } from '../router.js';
import { renderProfileAvatar, setProfileStatus } from '../components/profile-avatar.js';

export const renderProfile = () => {
  const summary = state.profileSummary;
  const user = summary?.user || state.pendingUser;
  const profilePosition = sanitizeDisplayRole(user?.job_description || '');

  renderProfileAvatar(user);
  profileName.textContent = user?.full_name || 'Пользователь';
  profileRole.textContent = profilePosition || 'Должность не указана';
  profileTotalAssessments.textContent = String(summary?.total_assessments || 0);
  profileAverageScore.textContent = summary?.average_score_percent != null ? summary.average_score_percent + '%' : '0%';
  profileFullName.value = user?.full_name || '';
  profileEmail.value = user?.email || '';
  profilePhone.value = user?.phone || 'Не указан';
  profileTelegram.value = user?.telegram || '';
  profileJobDescription.value = profilePosition || 'Не указана';
  profileCompanyIndustry.value = sanitizeDisplayMetaText(user?.company_industry || '') || 'Не указана';
};

export const saveProfile = async (options = {}) => {
  const { silent = false, successMessage = 'Изменения сохранены.' } = options;
  if (!state.pendingUser?.id) {
    setProfileStatus('Не удалось определить пользователя для сохранения профиля.', 'error');
    return;
  }

  const ownerId = state.pendingUser.id;
  const epoch = state.identityEpoch;
  profileEmail.disabled = true;
  profileTelegram.disabled = true;
  if (!silent) {
    setProfileStatus('Сохраняем изменения...', '');
  }

  try {
    const response = await fetch('/users/' + state.pendingUser.id + '/profile', {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        email: profileEmail.value.trim() || null,
        telegram: profileTelegram.value.trim() || null,
        avatar_data_url: state.profileAvatarDraft,
      }),
    });
    const data = await readApiResponse(response, 'Не удалось сохранить изменения профиля.');
    if (state.pendingUser?.id !== ownerId || state.identityEpoch !== epoch) return;
    state.pendingUser = data;
    if (state.profileSummary?.user) {
      state.profileSummary.user = data;
    }
    state.profileAvatarDraft = data.avatar_data_url || null;
    renderProfile();
    if (!silent || successMessage) {
      setProfileStatus(successMessage, 'success');
    }
  } catch (error) {
    if (state.pendingUser?.id !== ownerId || state.identityEpoch !== epoch) return;
    setProfileStatus(error.message, 'error');
  } finally {
    profileEmail.disabled = false;
    profileTelegram.disabled = false;
  }
};

export const loadProfileSummary = async () => {
  if (!state.pendingUser?.id) {
    throw new Error('Не удалось определить пользователя для загрузки профиля.');
  }
  const ownerId = state.pendingUser.id;
  const epoch = state.identityEpoch;
  const response = await fetch('/users/' + ownerId + '/profile-summary');
  const data = await readApiResponse(response, 'Не удалось загрузить профиль пользователя.');
  if (state.pendingUser?.id !== ownerId || state.identityEpoch !== epoch) throw new Error('Сессия профиля изменилась.');
  state.profileSummary = data;
  state.profileHistoryPage = 1;
};

export const openProfile = async () => {
  const epoch = state.identityEpoch;
  setCurrentScreen('profile');
  persistAssessmentContext();
  syncUrlState('profile');
  hideAllPanels();
  profilePanel.classList.remove('hidden');
  state.profileSummary = null;
  state.profileAvatarDraft = null;
  for (const field of [profileFullName, profileEmail, profilePhone, profileTelegram, profileJobDescription, profileCompanyIndustry]) field.value = '';
  profileName.textContent = '';
  profileRole.textContent = 'Загружаем профиль…';
  profileTotalAssessments.textContent = '0';
  profileAverageScore.textContent = '0%';
  setProfileStatus('', '');
  renderProfileAvatar(null);
  try {
    await loadProfileSummary();
    state.profileAvatarDraft =
      state.profileSummary?.user?.avatar_data_url || state.pendingUser?.avatar_data_url || null;
    setProfileStatus('', '');
    renderProfile();
  } catch (error) {
    if (state.identityEpoch !== epoch) return;
    profileRole.textContent = error.message;
  }
};
