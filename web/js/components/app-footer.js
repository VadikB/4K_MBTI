const CHAT_PANEL_IDS = new Set(['chat-panel', 'interview-panel', 'onboarding-panel']);
const ENTRY_PANEL_IDS = new Set(['session-restore-panel', 'auth-panel', 'auth-complete-panel']);

export const shouldShowAppFooter = (panelId) => Boolean(panelId && !CHAT_PANEL_IDS.has(panelId));
export const shouldShowEntryHeader = (panelId) => ENTRY_PANEL_IDS.has(panelId);
export const shouldShowFooterRelease = (panelId) => Boolean(panelId && !ENTRY_PANEL_IDS.has(panelId));

const findVisiblePanel = (root) => Array.from(root.querySelectorAll('.shell > .panel'))
  .find((panel) => !panel.classList.contains('hidden'));

export const initAppFooter = ({ root = document, now = new Date() } = {}) => {
  const footer = root.querySelector('.app-footer');
  if (!footer) return () => {};
  const entryHeader = root.querySelector('[data-entry-header]');

  const year = footer.querySelector('[data-app-footer-year]');
  if (year) year.textContent = String(now.getFullYear());

  const syncVisibility = () => {
    const visiblePanel = findVisiblePanel(root);
    const visible = shouldShowAppFooter(visiblePanel?.id);
    footer.classList.toggle('hidden', !visible);
    footer.setAttribute('aria-hidden', visible ? 'false' : 'true');
    footer.querySelector('.app-footer-release')?.classList.toggle(
      'hidden',
      !shouldShowFooterRelease(visiblePanel?.id),
    );
    if (entryHeader) {
      const headerVisible = shouldShowEntryHeader(visiblePanel?.id);
      entryHeader.classList.toggle('hidden', !headerVisible);
      entryHeader.setAttribute('aria-hidden', headerVisible ? 'false' : 'true');
    }
  };

  const panels = Array.from(root.querySelectorAll('.shell > .panel'));
  const observer = new MutationObserver(syncVisibility);
  panels.forEach((panel) => observer.observe(panel, { attributes: true, attributeFilter: ['class'] }));
  syncVisibility();

  return () => observer.disconnect();
};
