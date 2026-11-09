const CHAT_PANEL_IDS = new Set(['chat-panel', 'interview-panel', 'onboarding-panel']);

export const shouldShowAppFooter = (panelId) => Boolean(panelId && !CHAT_PANEL_IDS.has(panelId));

const findVisiblePanel = (root) => Array.from(root.querySelectorAll('.shell > .panel'))
  .find((panel) => !panel.classList.contains('hidden'));

export const initAppFooter = ({ root = document, now = new Date() } = {}) => {
  const footer = root.querySelector('.app-footer');
  if (!footer) return () => {};

  const year = footer.querySelector('[data-app-footer-year]');
  if (year) year.textContent = String(now.getFullYear());

  const syncVisibility = () => {
    const visiblePanel = findVisiblePanel(root);
    const visible = shouldShowAppFooter(visiblePanel?.id);
    footer.classList.toggle('hidden', !visible);
    footer.setAttribute('aria-hidden', visible ? 'false' : 'true');
    const isAuth = visiblePanel?.id === 'auth-panel' || visiblePanel?.id === 'session-restore-panel';
    footer.querySelector('.app-footer-release')?.classList.toggle('hidden', isAuth);
  };

  const panels = Array.from(root.querySelectorAll('.shell > .panel'));
  const observer = new MutationObserver(syncVisibility);
  panels.forEach((panel) => observer.observe(panel, { attributes: true, attributeFilter: ['class'] }));
  syncVisibility();

  return () => observer.disconnect();
};
