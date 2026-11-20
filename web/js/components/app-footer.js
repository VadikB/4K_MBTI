const CHAT_PANEL_IDS = new Set(['chat-panel', 'interview-panel', 'onboarding-panel']);

export const shouldShowAppFooter = (panelId, standalone = false) => Boolean(panelId && (standalone || !CHAT_PANEL_IDS.has(panelId)));

const findVisiblePanel = (root) => Array.from(root.querySelectorAll('.shell > .panel'))
  .find((panel) => !panel.classList.contains('hidden'));

export const initAppFooter = ({ root = document, now = new Date() } = {}) => {
  const footer = root.querySelector('.app-footer');
  if (!footer) return () => {};

  const year = footer.querySelector('[data-app-footer-year]');
  if (year) year.textContent = String(now.getFullYear());

  const syncVisibility = () => {
    const visiblePanel = findVisiblePanel(root);
    const visible = shouldShowAppFooter(visiblePanel?.id, visiblePanel?.matches('.onboarding-standalone, .product-answer-screen'));
    footer.classList.toggle('hidden', !visible);
    const interview = Boolean(visiblePanel?.classList.contains('product-answer-screen'));
    footer.classList.toggle('app-footer--participant', interview || visiblePanel?.id === 'dashboard-panel');
    footer.classList.toggle('app-footer--interview', interview);
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
