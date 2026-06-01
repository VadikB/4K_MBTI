const moduleCache = new Map();
const initialized = new Set();

const loadModule = (key, loader) => {
  if (!moduleCache.has(key)) {
    moduleCache.set(key, loader());
  }
  return moduleCache.get(key);
};

export const loadChat = () => loadModule('chat', () => import('./entries/chat.js'));
export const loadProcessing = () => loadModule('processing', () => import('./entries/processing.js'));
export const loadReport = async () => {
  const module = await loadModule('report', () => import('./entries/report.js'));
  if (!initialized.has('report')) {
    module.initReport();
    initialized.add('report');
  }
  return module;
};
export const loadOnboarding = async () => {
  const module = await loadModule('onboarding', () => import('./entries/onboarding.js'));
  if (!initialized.has('onboarding')) {
    module.initOnboarding();
    initialized.add('onboarding');
  }
  return module;
};
export const loadAiWelcome = () => loadModule('ai-welcome', () => import('./entries/ai-welcome.js'));
export const loadProfile = () => loadModule('profile', () => import('./entries/profile.js'));
export const loadReports = () => loadModule('reports', () => import('./entries/reports.js'));
export const loadDashboard = () => loadModule('dashboard', () => import('./entries/dashboard.js'));
export const loadAssessment = () => loadModule('assessment', () => import('./entries/assessment.js'));
export const loadInterview = async () => {
  const module = await loadModule('interview', () => import('./entries/interview.js'));
  if (!initialized.has('interview')) {
    module.initInterview();
    initialized.add('interview');
  }
  return module;
};
export const loadAdminDashboard = () =>
  loadModule('admin-dashboard', () => import('./entries/admin-dashboard.js'));
export const loadAdminPromptLab = () =>
  loadModule('admin-prompt-lab', () => import('./entries/admin-prompt-lab.js'));
export const loadAdminReports = () =>
  loadModule('admin-reports', () => import('./entries/admin-reports.js'));
export const loadAdminMethodology = async () => {
  const module = await loadModule('admin-methodology', () => import('./entries/admin-methodology.js'));
  if (!initialized.has('admin-methodology')) {
    module.initAdminMethodology();
    initialized.add('admin-methodology');
  }
  return module;
};
export const loadAdminReportDetail = () =>
  loadModule('admin-report-detail', () => import('./entries/admin-report-detail.js'));

export const resetChatScreen = async () => {
  const module = await loadChat();
  module.resetChat();
};

export const openProcessingScreen = async () => {
  const module = await loadProcessing();
  module.openProcessing();
};

export const openReportScreen = async () => {
  const module = await loadReport();
  module.openReport();
};

export const loadSkillAssessmentsForReport = async () => {
  const module = await loadReport();
  return module.loadSkillAssessments();
};

export const openOnboardingScreen = async () => {
  const module = await loadOnboarding();
  module.openOnboarding();
};

export const openWelcomeScreenLazy = async () => {
  const module = await loadAiWelcome();
  module.openWelcomeScreen();
};

export const openPrechatScreen = async () => {
  const module = await loadAiWelcome();
  module.openPrechat();
};

export const openChatScreen = async () => {
  const module = await loadChat();
  module.openChat();
};

export const openProfileScreen = async () => {
  const module = await loadProfile();
  await module.openProfile();
};

export const openReportsScreen = async () => {
  const module = await loadReports();
  await module.openReports();
};

export const openAdminDashboardScreen = async () => {
  const module = await loadAdminDashboard();
  module.openAdminDashboard();
};

export const loadAdminDashboardData = async (periodKey) => {
  const module = await loadAdminDashboard();
  return module.loadAdminDashboard(periodKey);
};

export const openAdminPromptLabScreen = async () => {
  const module = await loadAdminPromptLab();
  await module.openAdminPromptLab();
};

export const openAdminReportsScreen = async () => {
  const module = await loadAdminReports();
  await module.openAdminReports();
};

export const loadAdminReportsData = async () => {
  const module = await loadAdminReports();
  return module.loadAdminReports();
};

export const openAdminMethodologyScreen = async () => {
  const module = await loadAdminMethodology();
  await module.openAdminMethodology();
};

export const loadAdminMethodologyData = async () => {
  const module = await loadAdminMethodology();
  return module.loadAdminMethodology();
};

export const openAdminReportDetailScreen = async (sessionId) => {
  const module = await loadAdminReportDetail();
  await module.openAdminReportDetail(sessionId);
};
