import { loadInterview } from './screen-loaders.js';
import { APP_RELEASE } from './config.js';
import { appReleaseNumber, authPanel, emailInput, authTokenForm, magicTokenInput, authStatus, authError } from './dom.js';
import {
  state,
  safeStorage,
  STORAGE_KEYS,
  restoreAssessmentContext,
  restoreAssessmentContextFromParams,
  clearAssessmentContext,
  applyJourneyAssessmentContext,
  persistAssessmentContext,
} from './state.js';
import {
  restoreServerSession,
  restoreLocalUserSession,
  loadUserJourneyState,
  resetStaleUserState,
} from './session.js';
import {
  advanceSessionGeneration,
  installSessionRequestTracking,
  registerUnauthorizedResponseHandler,
} from './api.js';
import { hideAllPanels, returnToStart, openAcquaintanceWaiting } from './router.js';
import { initAppFooter } from './components/app-footer.js';
import { activateOrganizationInvitation, handleAuthActionToken, initWiring, verifyEmailMagicLinkToken } from './wiring.js';
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
  openAdminOrganizationsScreen,
  loadAdminOrganizationsData,
  openAdminRegressionTestsScreen,
  openAdminPromptLabScreen,
  openAdminReportsScreen,
  loadAdminReportsData,
  openAdminMethodologyScreen,
  loadAdminMethodologyData,
  openAdminReportDetailScreen,
  loadDashboard,
} from './screen-loaders.js';

if (appReleaseNumber) {
  appReleaseNumber.textContent = APP_RELEASE;
}

const syncRuntimeReleaseNumber = async () => {
  if (!appReleaseNumber) {
    return;
  }
  try {
    const response = await fetch('/users/version', {
      credentials: 'same-origin',
    });
    if (!response.ok) {
      return;
    }
    const payload = await response.json();
    const runtimeVersion = String(payload?.version || '').trim();
    if (runtimeVersion) {
      appReleaseNumber.textContent = runtimeVersion;
    }
  } catch (_error) {
    // keep fallback release number from the frontend config
  }
};

installSessionRequestTracking();
initWiring();
initAppFooter();
void syncRuntimeReleaseNumber();

const resetInitialState = () => {
  advanceSessionGeneration({ broadcast: false });
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
  if (authTokenForm) {
    authTokenForm.classList.add('hidden');
  }
  if (authStatus) {
    authStatus.textContent = '';
    authStatus.classList.add('hidden');
  }
  if (magicTokenInput) {
    magicTokenInput.value = '';
  }
  if (emailInput) {
    emailInput.disabled = false;
    emailInput.focus();
  }
};

registerUnauthorizedResponseHandler(resetStaleUserState);

const bootApp = async () => {
  resetInitialState();
  const params = new URLSearchParams(window.location.search);
  const authTokenFromLink = String(params.get('token') || '').trim();
  const authAction = String(params.get('auth_action') || '').trim();
  let invitationToken = String(params.get('invite') || '').trim();
  if (authAction === 'password_reset') {
    try { window.sessionStorage.removeItem('agent4k.organizationInvitationToken'); } catch (_error) { /* optional */ }
    invitationToken = '';
  } else if (!invitationToken) {
    try { invitationToken = String(window.sessionStorage.getItem('agent4k.organizationInvitationToken') || '').trim(); } catch (_error) { /* optional */ }
  }
  if (invitationToken && !authTokenFromLink) {
    try {
      const organization = await activateOrganizationInvitation(invitationToken);
      if (organization?.personal) {
        // A personal invitation is a complete, priority auth route. Do not let
        // stale local state or another server session replace its recipient.
        return;
      }
    } catch (error) {
      try { window.sessionStorage.removeItem('agent4k.organizationInvitationToken'); } catch (_storageError) { /* optional */ }
      if (authError) {
        authError.textContent = error.message;
        authError.hidden = false;
      }
    }
  }
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
  if (authTokenFromLink) {
    if (authTokenForm) {
      authTokenForm.classList.remove('hidden');
    }
    if (magicTokenInput) {
      magicTokenInput.value = authTokenFromLink;
    }
    if (authStatus) {
      authStatus.textContent = 'Подтверждаем ссылку для входа...';
      authStatus.classList.remove('hidden');
    }
    window.history.replaceState({}, '', '/?ui=' + Date.now());
    if (authAction === 'email_verification' || authAction === 'password_reset') {
      await handleAuthActionToken(authAction, authTokenFromLink);
    } else {
      await verifyEmailMagicLinkToken(authTokenFromLink);
    }
    return;
  }
  if (screen && screen !== 'processing' && screen !== 'report') {
    state.currentScreen = screen;
  }
  const hadStoredPendingUser = Boolean(state.pendingUser?.id);
  let restoredServerSession = false;

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

  if (state.canAdmin && !state.adminDashboard?.is_superadmin && screen) {
    if (screen.startsWith('admin')) {
      state.activeArea = 'management';
      state.isAdmin = true;
    } else if (
      ['auth-complete', 'onboarding', 'dashboard', 'ai-welcome', 'prechat', 'interview', 'profile', 'reports', 'processing', 'chat'].includes(screen)
      || (screen === 'report' && params.get('report_access') !== 'customer')
    ) {
      state.activeArea = 'assessment';
      state.isAdmin = false;
    }
    persistAssessmentContext();
  }

  if (state.pendingUser?.id) {
    if (state.currentScreen === 'admin-prompt-lab' && state.isAdmin) {
      void openAdminPromptLabScreen();
      return;
    }
    if (screen === 'report' && state.isAdmin && params.get('report_access') === 'customer'
      && params.get('cycle_id') && params.get('report_id')) {
      await openReportScreen({
        m8CycleId: params.get('cycle_id'),
        m8ReportId: params.get('report_id'),
        customerAccess: true,
      });
      return;
    }
    if (state.currentScreen === 'admin-organizations' && state.isAdmin) {
      try {
        await loadAdminOrganizationsData();
      } catch (error) {
        console.error('Failed to restore admin organizations', error);
      }
      void openAdminOrganizationsScreen();
      return;
    }
    if (state.currentScreen === 'admin-regression-tests' && state.isAdmin) {
      void openAdminRegressionTestsScreen();
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
    if (!state.isAdmin) {
      try {
        const requestedM8CycleId = screen === 'report' ? params.get('cycle_id') : null;
        const requestedLegacyReportSessionId = screen === 'report' && !requestedM8CycleId
          ? Number(params.get('session_id') || state.assessmentSessionId) || null : null;
        const journey = await loadUserJourneyState();
        applyJourneyAssessmentContext(journey);
        if (journey?.next_action === 'wait_for_acquaintance_data') {
          openAcquaintanceWaiting(journey.acquaintance?.readiness);
          return;
        }
        if (requestedLegacyReportSessionId) {
          state.assessmentSessionId = requestedLegacyReportSessionId;
          await loadSkillAssessmentsForReport();
          await openReportScreen();
          return;
        }
        if (
          screen === 'report'
          && !requestedLegacyReportSessionId
          && (requestedM8CycleId || (journey?.report_status === 'ready' && state.productCycleId))
        ) {
          await openReportScreen({
            m8CycleId: requestedM8CycleId || state.productCycleId,
            m8ReportId: params.get('report_id'),
            returnTarget: params.get('report_id') ? 'reports' : 'home',
          });
          return;
        }
        if (journey?.next_action === 'complete_profile') {
          const profileRecovery = await import('./screens/profile-recovery.js');
          await profileRecovery.recoverProfileCompletionForAssessment({ resumeAssessment: false });
          return;
        }
        if (journey?.next_action === 'show_onboarding') {
          await openOnboardingScreen({
            currentStep: Number(journey.onboarding?.current_step || 0),
          });
          return;
        }
        if (journey?.next_action === 'resume_assessment' && state.assessmentRuntimeKind === 'cycle' && state.productCycleId) {
          const response = await fetch('/users/assessment/cycles/' + encodeURIComponent(state.productCycleId) + '/runtime', { credentials: 'same-origin' });
          if (!response.ok) throw new Error('Cycle runtime is not available');
          (await loadInterview()).openInterview();
          return;
        }
        if (journey?.next_action === 'resume_assessment' && state.assessmentSessionCode) {
          await openPrechatScreen();
          return;
        }
        if (['show_processing', 'show_assessment_error'].includes(journey?.next_action)) {
          await openProcessingScreen({
            initialCycleSnapshot: state.assessmentRuntimeKind === 'cycle' ? {
              results_status: journey?.assessment?.status === 'failed' ? 'failed' : 'processing',
              report_status: journey?.report_status || 'not_ready',
            } : null,
          });
          return;
        }
        if (journey?.next_action === 'show_dashboard') {
          if (screen === 'report') {
            const m8CycleId = params.get('cycle_id');
            if (m8CycleId) {
              await openReportScreen({ m8CycleId, m8ReportId: params.get('report_id'), returnTarget: params.get('report_id') ? 'reports' : 'home' });
              return;
            }
            if (state.assessmentSessionId) {
              await loadSkillAssessmentsForReport();
              await openReportScreen();
              return;
            }
          }
          if (state.currentScreen === 'profile') {
            await openProfileScreen();
            return;
          }
          if (state.currentScreen === 'reports') {
            await openReportsScreen();
            return;
          }
          const dashboardModule = await loadDashboard();
          dashboardModule.openDashboard();
          return;
        }
        throw new Error(`Unknown journey action: ${journey?.next_action || 'empty'}`);
      } catch (error) {
        console.error('Failed to route by server journey state', error);
        returnToStart();
        if (authError) {
          authError.textContent = 'Не удалось определить актуальный этап. Обновите страницу или повторите вход.';
          authError.hidden = false;
        }
        return;
      }
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
