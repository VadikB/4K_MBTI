import { APP_RELEASE } from './config.js';
import { appReleaseNumber, authPanel, phoneInput } from './dom.js';
import {
  state,
  safeStorage,
  STORAGE_KEYS,
  restoreAssessmentContext,
  restoreAssessmentContextFromParams,
  clearAssessmentContext,
} from './state.js';
import { restoreServerSession, restoreLocalUserSession } from './session.js';
import { hideAllPanels, returnToStart } from './router.js';
import { initWiring } from './wiring.js';
import {
  openProcessingScreen,
  openReportScreen,
  loadSkillAssessmentsForReport,
  openOnboardingScreen,
  openWelcomeScreenLazy,
  openPrechatScreen,
  openChatScreen,
  openProfileScreen,
  openReportsScreen,
  openAdminDashboardScreen,
  loadAdminDashboardData,
  openAdminPromptLabScreen,
  openAdminReportsScreen,
  loadAdminReportsData,
  openAdminMethodologyScreen,
  loadAdminMethodologyData,
  openAdminReportDetailScreen,
} from './screen-loaders.js';

if (appReleaseNumber) {
  appReleaseNumber.textContent = APP_RELEASE;
}

initWiring();

const resetInitialState = () => {
  state.sessionId = null;
  state.completed = false;
  state.isChatSubmitting = false;
  state.pendingAgentMessage = null;
  state.pendingActionOptions = [];
  state.pendingConsentTitle = null;
  state.pendingConsentText = null;
  state.pendingUser = null;
  state.dashboard = null;
  state.isAdmin = false;
  state.adminDashboard = null;
  state.pendingRoleOptions = [];
  state.pendingNoChangesQuickReply = false;
  state.assessmentSessionCode = null;
  state.assessmentSessionId = null;
  state.assessmentTotalCases = 0;
  state.currentScreen = 'auth';
  hideAllPanels();
  authPanel.classList.remove('hidden');
  if (phoneInput) {
    phoneInput.disabled = false;
    phoneInput.focus();
  }
};

const bootApp = async () => {
  resetInitialState();
  const params = new URLSearchParams(window.location.search);
  if (params.get('reset') === '1') {
    clearAssessmentContext();
    try {
      await fetch('/users/session/logout', {
        method: 'POST',
        credentials: 'same-origin',
      });
    } catch (_error) {
      // ignore reset cleanup network issues
    }
    window.history.replaceState({}, '', '/?ui=' + Date.now());
  }
  const screen = params.get('screen') || (safeStorage.getItem(STORAGE_KEYS.completionPending) ? 'processing' : null);
  restoreAssessmentContext();
  restoreAssessmentContextFromParams(params);
  if (screen && screen !== 'processing' && screen !== 'report') {
    state.currentScreen = screen;
  }
  const hadStoredPendingUser = Boolean(state.pendingUser?.id);
  let restoredServerSession = false;

  if (screen === 'processing') {
    if (state.pendingUser?.id && state.assessmentSessionId) {
      await openProcessingScreen();
      return;
    }
  }

  if (screen === 'report') {
    if (state.pendingUser?.id && state.assessmentSessionId) {
      void (async () => {
        try {
          await loadSkillAssessmentsForReport();
          await openReportScreen();
        } catch (error) {
          console.error('Failed to open report screen', error);
          returnToStart();
        }
      })();
      return;
    }
  }

  if (!state.pendingUser?.id) {
    try {
      restoredServerSession = await restoreServerSession();
    } catch (error) {
      console.error('Failed to restore server session', error);
    }
  }

  if ((hadStoredPendingUser || !restoredServerSession) && state.pendingUser?.id) {
    try {
      await restoreLocalUserSession();
    } catch (error) {
      console.error('Failed to restore local user session', error);
    }
  }

  if (state.pendingUser?.id) {
    if (state.currentScreen === 'onboarding') {
      await openOnboardingScreen();
      return;
    }
    if (state.currentScreen === 'admin-prompt-lab' && state.isAdmin) {
      void openAdminPromptLabScreen();
      return;
    }
    if (state.currentScreen === 'admin-reports' && state.isAdmin) {
      try {
        await loadAdminReportsData();
      } catch (error) {
        console.error('Failed to restore admin reports', error);
      }
      void openAdminReportsScreen();
      return;
    }
    if (state.currentScreen === 'admin-methodology' && state.isAdmin) {
      try {
        await loadAdminMethodologyData();
      } catch (error) {
        console.error('Failed to restore admin methodology', error);
      }
      void openAdminMethodologyScreen();
      return;
    }
    if (state.currentScreen === 'admin-report-detail' && state.isAdmin && state.adminReportDetailSessionId) {
      void openAdminReportDetailScreen(state.adminReportDetailSessionId);
      return;
    }
    if (state.currentScreen === 'admin' && state.isAdmin) {
      if (state.isAdmin) {
        try {
          await loadAdminDashboardData(state.adminPeriodKey || '30d');
        } catch (error) {
          console.error('Failed to restore admin dashboard', error);
        }
      }
      await openAdminDashboardScreen();
      return;
    }
    if (state.currentScreen === 'interview' && state.assessmentSessionCode) {
      await openPrechatScreen();
      return;
    }
    if (state.currentScreen === 'profile') {
      void openProfileScreen();
      return;
    }
    if (state.currentScreen === 'reports') {
      void openReportsScreen();
      return;
    }
    if (state.currentScreen === 'chat' && state.sessionId) {
      await openChatScreen();
      return;
    }
    if (state.currentScreen === 'prechat') {
      await openPrechatScreen();
      return;
    }
    if (state.currentScreen === 'dashboard' || state.currentScreen === 'ai-welcome' || state.dashboard) {
      await openWelcomeScreenLazy();
      return;
    }
  }

  returnToStart();
};

window.addEventListener('popstate', () => {
  void bootApp();
});

void bootApp();
