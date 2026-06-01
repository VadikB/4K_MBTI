(function () {
  const screens = [
    { id: 'auth', label: 'Auth', group: 'Entry', panel: 'auth-panel' },
    { id: 'onboarding', label: 'Onboarding', group: 'Entry', panel: 'onboarding-panel' },
    { id: 'ai-welcome', label: 'Welcome First Use', group: 'Entry', panel: 'ai-welcome-panel' },
    { id: 'dashboard', label: 'Home', group: 'User', panel: 'dashboard-panel' },
    { id: 'chat', label: 'Profile Chat', group: 'User', panel: 'chat-panel' },
    { id: 'prechat', label: 'Assessment Welcome', group: 'Assessment', panel: 'prechat-panel' },
    { id: 'interview', label: 'Interview', group: 'Assessment', panel: 'interview-panel' },
    { id: 'processing', label: 'Processing', group: 'Assessment', panel: 'processing-panel' },
    { id: 'report', label: 'Report', group: 'Assessment', panel: 'report-panel' },
    { id: 'profile', label: 'Profile', group: 'User', panel: 'profile-panel' },
    { id: 'reports', label: 'Report History', group: 'User', panel: 'reports-panel' },
    { id: 'admin', label: 'Admin Dashboard', group: 'Admin', panel: 'admin-panel' },
    { id: 'admin-methodology-passports', label: 'Case Passports', group: 'Admin', panel: 'admin-methodology-panel' },
    { id: 'admin-methodology-library', label: 'Case Library', group: 'Admin', panel: 'admin-methodology-panel' },
    { id: 'admin-methodology-branches', label: 'Branches & Coverage', group: 'Admin', panel: 'admin-methodology-panel' },
    { id: 'admin-prompt-lab-cases', label: 'Prompt Lab Cases', group: 'Admin', panel: 'admin-prompt-lab-panel' },
    { id: 'admin-prompt-lab-dialog', label: 'Prompt Lab Dialog', group: 'Admin', panel: 'admin-prompt-lab-panel' },
    { id: 'admin-reports', label: 'Admin Reports', group: 'Admin', panel: 'admin-reports-panel' },
    { id: 'admin-report-detail', label: 'Admin Report Detail', group: 'Admin', panel: 'admin-report-detail-panel' },
  ];

  const frame = document.getElementById('screen-frame');
  const list = document.getElementById('screen-list');
  const label = document.getElementById('current-screen-label');
  const idLabel = document.getElementById('current-screen-id');
  const openFrameLink = document.getElementById('open-frame-link');
  let activeScreen = new URLSearchParams(window.location.search).get('screen') || screens[0].id;

  const html = (value) => String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');

  const injectPreviewStyles = (doc) => {
    if (doc.getElementById('screen-preview-style')) return;
    const style = doc.createElement('style');
    style.id = 'screen-preview-style';
    style.textContent = [
      '.screen-preview-watermark{position:fixed;right:14px;bottom:14px;z-index:9999;padding:8px 10px;border-radius:8px;background:rgba(15,23,42,.78);color:#fff;font:700 12px Inter,Arial,sans-serif;letter-spacing:.03em;text-transform:uppercase;pointer-events:none}',
    ].join('\n');
    doc.head.appendChild(style);
  };

  const clearAppStorage = () => {
    try {
      Object.keys(window.localStorage)
        .filter((key) => key.startsWith('agent4k.'))
        .forEach((key) => window.localStorage.removeItem(key));
    } catch (_error) {
      // Preview should still render if storage is unavailable.
    }
  };

  const decorateCanvas = (doc) => {
    injectPreviewStyles(doc);
    let watermark = doc.querySelector('.screen-preview-watermark');
    if (!watermark) {
      watermark = doc.createElement('div');
      watermark.className = 'screen-preview-watermark';
      doc.body.appendChild(watermark);
    }
    watermark.textContent = 'Preview only';
  };

  const applyVariant = (doc, screenId) => {
    decorateCanvas(doc);
    if (screenId.startsWith('admin-methodology') && doc.querySelector('#admin-methodology-panel.hidden')) {
      doc.querySelector('#admin-open-methodology-button')?.click();
      return;
    }
    if (screenId === 'admin-methodology-library') {
      doc.querySelector('#admin-methodology-tab-library')?.click();
    }
    if (screenId === 'admin-methodology-branches') {
      doc.querySelector('#admin-methodology-tab-branches')?.click();
    }
    if (screenId.startsWith('admin-prompt-lab') && doc.querySelector('#admin-prompt-lab-panel.hidden')) {
      doc.querySelector('#admin-open-prompt-lab-button')?.click();
      return;
    }
    if (screenId === 'admin-prompt-lab-dialog') {
      doc.querySelector('#admin-prompt-lab-tab-dialog')?.click();
    }
    if ((screenId === 'admin-reports' || screenId === 'admin-report-detail') && doc.querySelector('#admin-reports-panel.hidden')) {
      doc.querySelector('#admin-open-reports-button')?.click();
      return;
    }
    if (screenId === 'admin-report-detail' && doc.querySelector('#admin-report-detail-panel.hidden')) {
      doc.querySelector('#admin-reports-list .admin-report-row')?.click();
    }
  };

  const renderNav = () => {
    list.innerHTML = '';
    let currentGroup = '';
    screens.forEach((screen) => {
      if (screen.group !== currentGroup) {
        currentGroup = screen.group;
        const group = document.createElement('div');
        group.className = 'screen-group';
        group.textContent = currentGroup;
        list.appendChild(group);
      }
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'screen-button';
      button.dataset.screen = screen.id;
      button.innerHTML = '<span>' + html(screen.label) + '</span><small>' + html(screen.panel.replace('-panel', '')) + '</small>';
      button.addEventListener('click', () => loadScreen(screen.id));
      list.appendChild(button);
    });
  };

  const loadScreen = (screenId) => {
    activeScreen = screens.some((screen) => screen.id === screenId) ? screenId : screens[0].id;
    const screen = screens.find((item) => item.id === activeScreen);
    window.history.replaceState({}, '', '/__screens?screen=' + encodeURIComponent(activeScreen));
    label.textContent = screen.label;
    idLabel.textContent = activeScreen;
    document.querySelectorAll('.screen-button').forEach((button) => {
      button.classList.toggle('active', button.dataset.screen === activeScreen);
    });
    clearAppStorage();
    const src = '/__screen-canvas?screen=' + encodeURIComponent(activeScreen) + '&ui=' + Date.now();
    openFrameLink.href = src;
    frame.src = src;
  };

  frame.addEventListener('load', () => {
    const screen = screens.find((item) => item.id === activeScreen) || screens[0];
    const applyCurrentPreview = () => {
      const doc = frame.contentDocument;
      if (!doc) return;
      applyVariant(doc, screen.id);
    };
    [250, 900, 1800, 2800, 4200].forEach((delay) => window.setTimeout(applyCurrentPreview, delay));
  });

  renderNav();
  loadScreen(activeScreen);
}());
