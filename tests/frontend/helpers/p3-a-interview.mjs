import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { assessmentRuntimeErrorMessage } from '../../../web/js/assessment-errors.js';

const source = fs.readFileSync(new URL('../../../web/js/screens/interview.js', import.meta.url), 'utf8');
const section = (start, end) => source.slice(source.indexOf(start), source.indexOf(end));

// Execute production presenter/delivery/submit functions with a small DOM,
// deterministic layout callbacks and injected HTTP responses. These fixtures do
// not prove browser geometry, software keyboards, or real backend/DB behavior.
export const createInterviewHarness = ({ animationFrame = true, storage = new Map() } = {}) => {
  const callbacks = new Map();
  const calls = [];
  const listeners = new Map();
  let nextCallback = 0;
  let nextOperation = 0;
  let fetchImpl = async () => { throw new Error('Unexpected fetch'); };
  const fetchCalls = [];
  const errors = [];
  let pollingResumes = 0;
  let viewGeneration = 0;
  const createOperationId = () => `00000000-0000-4000-8000-${String(++nextOperation).padStart(12, '0')}`;
  const enqueue = (callback) => { callbacks.set(++nextCallback, callback); return nextCallback; };
  class Element {
    constructor() {
      this.children = [];
      this.dataset = {};
      this.style = {};
      this.className = '';
      this.isConnected = false;
      this.listeners = new Map();
      const classes = new Set();
      this.classList = {
        add: (...names) => names.forEach((name) => classes.add(name)),
        remove: (...names) => names.forEach((name) => classes.delete(name)),
        contains: (name) => classes.has(name),
        toggle: (name, enabled = !classes.has(name)) => enabled ? classes.add(name) : classes.delete(name),
      };
    }
    appendChild(child) { this.children.push(child); child.parentElement = this; child.isConnected = true; return child; }
    remove() { if (this.parentElement) this.parentElement.children = this.parentElement.children.filter((child) => child !== this); this.isConnected = false; }
    focus() { this.focused = true; }
    append(...children) { children.forEach((child) => this.appendChild(child)); }
    set innerHTML(_value) { this.children.forEach((child) => { child.isConnected = false; }); this.children = []; }
    get firstChild() { return this.children[0] || null; }
    get lastElementChild() { return this.children.at(-1) || null; }
    setAttribute() {}
    addEventListener(name, handler) { this.listeners.set(name, handler); }
    querySelector(selector) {
      for (const child of this.children) {
        if (child.className.split(' ').includes(selector.slice(1))) return child;
        const nested = child.querySelector(selector);
        if (nested) return nested;
      }
      return null;
    }
    scrollIntoView() { assert.fail('History alignment must not scroll the outer document'); }
  }
  const messages = new Element();
  const shell = new Element();
  const area = new Element();
  area.clientHeight = 400;
  area.scrollTop = 0;
  Object.defineProperty(area, 'scrollHeight', {
    get: () => messages.children.reduce((height, child) => height
      + (child.className.includes('interview-message--situation') ? 1600 : 180), 0),
  });
  area.closest = () => shell;
  area.scrollTo = ({ top, behavior }) => {
    area.scrollTop = Math.max(0, Math.min(top, area.scrollHeight - area.clientHeight));
    calls.push({ top: area.scrollTop, behavior });
  };
  const button = new Element();
  const textarea = new Element();
  textarea.value = '';
  const state = { currentScreen: 'interview', productCycleId: 'cycle-a', activeInterviewCaseKey: null,
    pendingUser: { id: 8 }, identityEpoch: 1, assessmentRuntimeKind: 'cycle' };
  let leaveCleanup;
  const context = vm.createContext({
    state, HTMLElement: Element,
    assessmentRuntimeErrorMessage,
    getAssessmentViewGeneration: () => viewGeneration,
    advanceAssessmentViewGeneration: () => { viewGeneration += 1; },
    window: {
      requestAnimationFrame: animationFrame ? enqueue : undefined,
      cancelAnimationFrame: (id) => callbacks.delete(id),
      setTimeout: enqueue, clearTimeout: (id) => callbacks.delete(id),
      addEventListener: (name, handler) => listeners.set(name, handler),
      sessionStorage: { getItem: (key) => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value), removeItem: (key) => storage.delete(key) },
    },
    document: { createElement: () => new Element(), addEventListener() {} },
    MutationObserver: class { observe() {} },
    interviewMessages: messages, interviewScrollArea: area, interviewMessagesScroll: button,
    interviewTextarea: textarea, interviewCompactQuery: null, caseSidebarToggle: null,
    interviewPanel: new Element(), interviewCompleteActions: new Element(),
    interviewTimerBadge: new Element(), interviewSubmitButton: new Element(),
    interviewFinishButton: new Element(), interviewPauseButton: new Element(),
    interviewAdditionalButton: new Element(), interviewCaseStatus: new Element(),
    persistAssessmentContext() {},
    setCurrentScreen(screen) { state.currentScreen = screen; },
    syncUrlState() {}, hideAllPanels() {}, loadProductRuntime: async () => {},
    interviewError: new Element(),
    showError(_element, message) { errors.push(message); },
    createOperationId, crypto: { randomUUID: createOperationId },
    fetch: async (...args) => { fetchCalls.push(args); return fetchImpl(...args); },
    readApiResponse: async (response) => { if (!response.ok) { const error = new Error(`HTTP ${response.status}`); error.status = response.status; throw error; } return response.json(); },
    resumeProductRuntimePolling() { pollingResumes += 1; },
    renderInterviewMeta() {}, renderCaseProgress() {}, updateInterviewTimer() {},
    parseInterviewAssistantMessage() { return null; },
    disableTextareaAssistFeatures() {}, placeInterviewTimerBadge() {},
    registerLeaveInterviewCleanup(handler) { leaveCleanup = handler; },
    clearInterviewTimer() {}, stopProductPresence() {}, pauseAssessmentTimerIfNeeded() {},
  });
  vm.runInContext(`
    let activeInterviewDraftKey = null;
    let renderedProductMessages = null;
    let renderedProductCycleId = null;
    let confirmedProductInterviewSnapshot = null;
    let confirmedProductInterviewCanSend = false;
    const productInterviewRequests = new Map();
    let interviewScrollAlignmentGeneration = 0;
    let interviewScrollAlignmentFrame = null;
    let interviewScrollAlignmentTimers = [];
    ${section('const interviewDraftKey =', '\nconst payloadText =').replaceAll('export const ', 'const ')}
    ${section('const submitAssessmentMessage =', '\nexport const resumeProductRuntimePolling =')}
    ${section('export const openInterview =', '\nconst startAssessmentInterview =').replace('export const ', 'const ')}
    ${section('const payloadText =', '\nconst renderProductRuntime =')}
    ${section('const renderProductRuntime =', '\nconst heartbeatProductPresence =')}
    ${section('const renderInterviewStructuredBlock =', '\nexport const addInterviewMessage =')}
    ${section('export const addInterviewMessage =', '\nconst isInterviewNearBottom =').replaceAll('export const ', 'const ')}
    ${section('const isInterviewNearBottom =', '\nconst getCurrentCaseDropdownLabel =')}
    ${section('export const initInterview =', '\nexport { startAssessmentInterview').replace('export const ', 'const ')}
    globalThis.subject = {renderProductRuntime, addInterviewMessage, setInterviewMessageDeliveryState,
      scheduleInterviewScrollAlignment, scheduleInterviewBottomAlignment, cancelInterviewScrollAlignment,
      productEventText, initInterview, sendProductInterviewAnswer, readProductInterviewAnswer, isCycleAssessment,
      clearInterviewDraft, prepareProductInterviewAnswer, submitAssessmentMessage, openInterview,
      showInterviewRuntimeError, restoreInterviewActionControls, isCurrentInterviewDraftSaved};
  `, context);
  const flush = () => {
    while (callbacks.size) {
      const batch = [...callbacks]; callbacks.clear();
      batch.forEach(([, callback]) => callback());
    }
  };
  const snapshot = (turnCount = 0, situationId = 'as-a', cycleId = 'cycle-a') => ({
    cycle_id: cycleId,
    current_situation: { assessment_situation_id: situationId, status: 'active', participant_payload: { title: 'Synthetic AS' } },
    route: { positions: [] }, status: { collection_status: 'active', remaining_seconds: 7200 },
    trace: { turns: Array.from({ length: turnCount }, (_, i) => ({
      turn_id: `turn-${i}`, sequence_no: i + 1,
      speaker_type: i % 2 ? 'assessee' : 'character', content_text: `Synthetic saved turn ${i}`,
    })), events: [] },
  });
  return { subject: context.subject, messages, area, button, textarea, state, callbacks, calls,
    listeners, flush, snapshot, storage, errors, fetchCalls, context,
    setFetch: (value) => { fetchImpl = value; },
    pollingResumes: () => pollingResumes, leave: () => leaveCleanup(),
    controls: { textarea, submit: context.interviewSubmitButton, finish: context.interviewFinishButton } };
};
