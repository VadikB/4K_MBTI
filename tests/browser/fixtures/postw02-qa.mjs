// Synthetic HTTP fixture only: no database, providers, mail or real participant data.
import { draftSlot } from "../../../web/js/answer-drafts.js";
export async function draftFixture(page, shared = null) {
  page.on('dialog', (dialog) => dialog.accept());
  const user = { id: 8, email: 'synthetic@example.test', full_name: 'Участник' };
  const initialModel = { cycle_id: 'synthetic-cycle',
    participant_progress: { planned_total: 8, current_position_no: 3, last_completed_position_no: 2 },
    status: { collection_status: 'active', remaining_seconds: 7200, deadline: '2026-11-20T12:00:00Z' },
    route: { positions: [{ position_no: 3, state: 'in_progress', current_assessment_situation_id: 'synthetic-as' }],
      progress: { total_positions: 8, completed_positions: null } },
    current_situation: { assessment_situation_id: 'synthetic-as', status: 'active', participant_payload: {
      title: 'Рабочая ситуация', introduction: 'Команда готовит запуск сервиса.',
      initial_situation: 'Клиенту нужно согласовать план. Собеседник предлагает обсудить доступные варианты.',
      assessee_task: 'Обсудите запрос и предложите следующий шаг.',
      initial_materials: [{ material_id: 'public-material', title: 'Доступные сведения', text: 'На проверку данных нужен один рабочий день.' }],
    } }, trace: { turns: [
      { turn_id: 'saved-question', sequence_no: 1, speaker_type: 'character', speaker_name: 'Собеседник', content_text: 'Какие шаги вы предложите?' },
      { turn_id: 'saved-answer', sequence_no: 2, speaker_type: 'assessee', content_text: 'Сначала уточню приоритеты, затем согласую план.' },
    ], events: [] } };
  const run = shared || { model: initialModel, drafts: {}, calls: [], unexpected: [], offline: false, returning: false, rejectAnswer: false };
  const model = run.model;
  await page.route('**/users/**', async (route) => {
    const req = route.request(), url = new URL(req.url()).pathname;
    run.calls.push({ url, method: req.method(), body: req.postDataJSON() });
    const json = (body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (url === '/users/version') return json({ version: '2.1.14' });
    if (url === '/users/session/restore') return json({ authenticated: true, user, dashboard: {} });
    if (url === '/users/8/session-bootstrap') return json({ user, dashboard: {} });
    if (url === '/users/8/journey-state') return json({ next_action: 'resume_assessment',
      assessment: { runtime_kind: 'cycle', cycle_id: model.cycle_id, assessment_situation_id: 'synthetic-as', status: 'active' },
      profile: { status: 'complete' }, onboarding: { status: 'completed' } });
    if (url.endsWith('/return-state')) return json(run.returning ? {
      cycle_id: model.cycle_id, current_assessment_situation_id: 'synthetic-as', current_assessment_situation_status: 'scenario_ended',
      position_no: 3, participant_progress: model.participant_progress,
      collection_status: 'active', allowed_action: 'continue_current', remaining_seconds: 7200,
      progress: { total_positions: 8 },
    } : { cycle_id: model.cycle_id, allowed_action: 'connected' });
    if (url.endsWith('/draft')) {
      if (run.draftOffline) return route.abort('failed');
      const slot = draftSlot(model);
      const saved = run.drafts[slot] ||= { version: 0, revision: '', text: '' };
      if (req.method() === 'PUT') {
        const data = req.postDataJSON();
        if (data.slot_id !== slot || data.expected_version !== saved.version) return json({detail:'DRAFT_VERSION_CONFLICT'}, 409);
        Object.assign(saved, { text: data.text, revision: data.revision, version: saved.version + 1 });
      }
      return json({ ...saved, owner_id: '8', cycle_id: model.cycle_id, assessment_situation_id: 'synthetic-as',
        slot_id: slot, expires_at: '2026-11-20T12:00:00Z' });
    }
    if (url.endsWith('/draft/accepted')) return json({ status: 'accepted' });
    if (url.endsWith('/answer-status')) {
      const query = new URL(req.url()).searchParams;
      return json({ cycle_id: model.cycle_id, assessment_situation_id: 'synthetic-as',
        request_id: query.get('request_id'), turn_id: query.get('turn_id'), clarification_id: null,
        status: run.receipt ? 'accepted' : 'absent', processing_status: run.receipt ? 'applied' : null,
        turn: run.receipt || null });
    }
    if (url.endsWith('/turns') && req.method() === 'POST') {
      const data = req.postDataJSON();
      run.receipt = { turn_id: data.turn_id, request_id: data.request_id,
        content_text: data.content, speaker_type: 'assessee', sequence_no: 10 };
      model.trace.turns.push(run.receipt);
      if (run.dropAnswer) return route.abort('failed');
      return json({ turn: run.receipt });
    }
    if (url.endsWith('/runtime')) return run.offline ? route.abort('failed') : json(model);
    if (url.endsWith('/transitions')) {
      model.current_situation.status = 'scenario_ended'; model.blocking_system_wait = true;
      model.finish_availability = { allowed: false, reason: 'ANALYSIS_PENDING' }; model.pipeline = { status: 'running' };
      return json({ status: 'scenario_ended' });
    }
    if (url.endsWith('/return-continue')) {
      run.returning = false;
      return json({ status: 'continued', assessment_situation_id: 'synthetic-as' });
    }
    if (url.endsWith('/presence')) return json({ heartbeat_interval_seconds: 10 });
    if (url.endsWith('/turns') && req.method() === 'POST' && run.rejectAnswer) return route.abort('failed');
    if (url.includes('/turns/') && url.endsWith('/outcome')) return json({ status: 'absent' });
    // Cabinet navigation is read-only; production dashboard may request history.
    if (url === '/users/8/assessment-cycle-history') return json({ cycles: [], reports: [] });
    run.unexpected.push(url);
    return json({ detail: `Unexpected ${url}` }, 500);
  });
  return run;
}

export async function dashboardFixture(page) {
  const user = { id: 8, email: 'synthetic@example.test', full_name: 'Участник' };
  const card = { cycle_id: 'cabinet-cycle', title: 'Оценка универсальных компетенций специалистов по сопровождению сложных межфункциональных проектов и работе с клиентами',
    organization_name: 'Синтетическая организация с длинным названием', status: 'active', journey_state: 'active',
    status_label: 'Оценка начата', description: 'Продолжите с того же места.', action: 'continue', button_label: 'Продолжить',
    completed_cases: null, total_cases: 8, planned_total: 8, current_position_no: 3, plan_revision_id: 'saved-plan', calendar_deadline: '2026-11-19T12:00:00Z' };
  const dashboard = { current_assessments: [card], completed_assessments: [{ ...card, cycle_id: 'previous-cycle', current_position_no: null,
    title: 'Предыдущее прохождение', status: 'report_ready', journey_state: 'report_ready', status_label: 'Результат готов',
    description: 'Результат доступен.', action: 'open_report', button_label: 'Посмотреть результат', report_id: 'saved-report', calendar_deadline: null, closed_at: '2026-11-10T12:00:00Z' }] };
  const model = { assignment_id: 91, assessment_name: card.title, readiness: { status: 'ready', organization_id: 10, assignment_ref: 'cabinet', questionnaire_revision_id: 41,
    briefing: { questions: ['Q1', 'Q2', 'Q3'], consent_version: 1 } }, mandatory_complete: true,
    state: { consent_version: 1, consent_accepted_at: 'synthetic', answers_json: { answer_1: 'A', answer_2: 'B', answer_3: 'C' } },
    onboarding: { status: 'completed', current_step: 8 }, late_readiness: { status: 'ready_to_prepare', personalized_profile_id: 4 },
    prepared_plan: { cycle_id: card.cycle_id, revision_id: card.plan_revision_id, start_readiness: { contract: 'm7_start_readiness/1', cycle_id: card.cycle_id, plan_revision_id: card.plan_revision_id, can_start: true, reasons: [] },
      plan: { route: Array.from({ length: 8 }, () => ({})), time_budget_seconds: 7200, calendar_window_seconds: 259200, participant_notice: 'Сохранённый методологический notice.' } } };
  const calls = [], unexpected = [];
  const journey = { next_action: 'show_dashboard', readFailure: false };
  const respond = (route, body) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) });
  await page.route('**/users/**', (route) => {
    const request = route.request(), pathname = new URL(request.url()).pathname;
    calls.push({ method: request.method(), pathname });
    if (pathname === '/users/version') return respond(route, { version: 'synthetic' });
    if (pathname === '/users/session/restore') return respond(route, { authenticated: true, user, dashboard });
    if (pathname === '/users/8/session-bootstrap') return journey.readFailure
      ? route.fulfill({ status: 503, contentType: 'application/json', body: '{}' }) : respond(route, { user, dashboard });
    if (pathname === '/users/8/journey-state') return respond(route, { next_action: journey.next_action, can_open_dashboard: true,
      profile: { status: 'complete' }, onboarding: model.onboarding, assessment: { status: 'in_progress', runtime_kind: 'cycle', cycle_id: card.cycle_id } });
    if (pathname.startsWith('/users/assessment/cycles/preparation/')) return respond(route, model.preparation_operation);
    if (pathname === '/users/8/acquaintance') return respond(route, model);
    if (pathname === '/users/assessment/m7/cycles/cabinet-cycle/return-state') return respond(route, {
      cycle_id: 'cabinet-cycle', position_no: 3, current_assessment_situation_id: 'same-saved-as', current_assessment_situation_status: 'active',
      allowed_action: 'continue_current', recognized_absence_seconds: 180, remaining_seconds: 1200,
      calendar_deadline: '2026-11-19T12:00:00Z', progress: { completed_positions: 2, total_positions: 8 },
      planned_positions: 8, planned_total: true,
    });
    unexpected.push(`${request.method()} ${pathname}`);
    return route.fulfill({ status: 500, body: 'Unexpected fixture request' });
  });
  return { dashboard, card, model, calls, unexpected, journey };
}

export const preparationModel = { operation_id: 'synthetic-preparation', kind: 'assessment', status: 'running',
  stage_label: 'Проверяем материалы ситуации', explanation: 'Проверяем, что ситуацию можно открыть для прохождения.',
  started_at: '2026-11-16T11:30:00Z', stage_started_at: '2026-11-16T11:33:00Z',
  last_progress_at: '2026-11-16T11:33:00Z', read_at: '2026-11-16T12:00:00Z',
  freshness: 'confirmed', delayed: true, delay_notice_seconds: 300, reference: 'P4K-1234567890ABCDEF12345678', allowed_actions: ['check'] };