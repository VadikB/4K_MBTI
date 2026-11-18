import { initAppHeader } from './app-header.js';

const headers = new WeakMap();
export const reportHeader = (panel) => {
  if (headers.has(panel)) return headers.get(panel);
  const root = panel.querySelector('[data-app-header]');
  const header = initAppHeader({ root, onHome: () => {
    void import('../screens/ai-welcome.js').then((module) => module.openHomePage());
  } });
  root.querySelector('[data-header-profile]').onclick = () => {
    void import('../screens/profile.js').then((module) => module.openProfile());
  };
  root.querySelector('[data-header-logout]').onclick = (event) => {
    void import('../session.js').then((module) => module.logoutAndReturnToStart(event.target));
  };
  headers.set(panel, header);
  return header;
};
