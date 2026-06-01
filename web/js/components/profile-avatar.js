import { state } from '../state.js';
import { profileAvatar, profileAvatarImage, profileSaveStatus } from '../dom.js';
import { buildInitials } from '../utils/format.js';

export const setProfileStatus = (text = '', tone = '') => {
  profileSaveStatus.textContent = text;
  profileSaveStatus.className = 'profile-save-status' + (tone ? ' ' + tone : '');
  profileSaveStatus.hidden = !text;
};

export const renderProfileAvatar = (user) => {
  const avatarDataUrl = state.profileAvatarDraft != null ? state.profileAvatarDraft : user?.avatar_data_url || null;

  profileAvatar.textContent = buildInitials(user?.full_name || 'Пользователь');
  if (avatarDataUrl) {
    profileAvatarImage.src = avatarDataUrl;
    profileAvatarImage.classList.remove('hidden');
    profileAvatar.classList.add('hidden');
    return;
  }

  profileAvatarImage.removeAttribute('src');
  profileAvatarImage.classList.add('hidden');
  profileAvatar.classList.remove('hidden');
};
