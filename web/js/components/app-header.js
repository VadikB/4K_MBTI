import { sanitizeDisplayRole } from '../utils/format.js';

// One identity projection for any shared header. Never substitute a prototype user.
export const appHeaderIdentity = (user) => {
  const fullName = typeof user?.full_name === 'string' ? user.full_name.trim().replace(/\s+/g, ' ') : '';
  const name = fullName || 'Участник';
  const initials = name.split(' ').slice(0, 2).map((part) => Array.from(part)[0].toLocaleUpperCase('ru-RU')).join('');
  return { name, initials, role: sanitizeDisplayRole(user?.job_description || '') };
};

// Enhance the existing shared topbar DOM; do not clone a cabinet-specific header.
export const initAppHeader = ({ root, onHome }) => {
  root.querySelectorAll('[data-header-home]').forEach((button) => {
    button.addEventListener('click', (event) => { event.preventDefault(); onHome(); });
  });
  return {
    updateUser(user) {
      const { name, initials, role } = appHeaderIdentity(user);
      root.querySelectorAll('[data-header-name]').forEach((node) => { node.textContent = name; });
      root.querySelector('[data-header-avatar]').textContent = initials;
      const roleNode = root.querySelector('[data-header-role]');
      if (roleNode) { roleNode.textContent = role; roleNode.style.display = role ? '' : 'none'; }
      const menu = root.querySelector('[data-header-user-menu]');
      menu.setAttribute('aria-label', `Меню пользователя: ${name}`);
      menu.title = name;
    },
  };
};
