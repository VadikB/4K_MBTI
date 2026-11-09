import fs from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const modes = new Set(['active-long', 'active-short', 'pause', 'return', 'unknown', 'recovered']);
const user = { id: 8, email: 'p3b-preview@example.test', full_name: 'Синтетический участник' };
const states = new Map();

const json = (response, value, status = 200) => {
  response.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
  response.end(JSON.stringify(value));
};

const modeFromRequest = (request) => {
  const cookie = String(request.headers.cookie || '').match(/(?:^|; )p3b_preview=([^;]+)/)?.[1];
  const mode = decodeURIComponent(cookie || 'active-long');
  return modes.has(mode) ? mode : 'active-long';
};

const scenario = (mode) => {
  const long = mode === 'active-long';
  const short = mode === 'active-short';
  const total = short ? 5 : 8;
  const position = short ? 2 : mode === 'pause' ? 3 : 1;
  const cycleId = `p3b-${mode}`;
  const asId = `p3b-as-${mode}`;
  return { cycleId, asId, total, position, completed: position - 1,
    remaining: mode === 'unknown' ? null : short ? 5400 : mode === 'pause' ? 3600 : 4200,
    long };
};

const runtime = (mode, continued) => {
  const s = scenario(mode);
  const repeatedText = 'Клиент просит ускорить согласование, а команда указывает на зависимость от проверки данных. ';
  return {
    runtime_kind: 'cycle', cycle_id: s.cycleId, between_situations: false,
    return_policy_enabled: true,
    status: { collection_status: 'active', remaining_seconds: s.remaining ?? 3600 },
    route: { positions: [{ position_no: s.position, state: 'in_progress', current_assessment_situation_id: s.asId }],
      progress: { completed_positions: s.completed, total_positions: s.total } },
    current_situation: { assessment_situation_id: s.asId, status: 'active', participant_payload: {
      title: s.long ? 'Согласование сложного запроса' : continued ? 'Сохранённая ситуация после Continue' : 'Разговор с клиентом',
      introduction: 'Синтетический сценарий для просмотра P3-B.',
      initial_situation: s.long ? repeatedText.repeat(12) : 'Клиент уточняет сроки и условия.',
      assessee_position: 'Вы отвечаете за согласование решения.',
      participants_and_positions: 'Клиент — инициатор запроса; коллега — владелец проверки.',
      assessee_task: s.long ? repeatedText.repeat(8) : 'Предложите следующий шаг.',
      conditions_and_constraints: 'Не обещайте срок без проверки.',
      initial_materials: [{ title: 'Справка', text: s.long ? repeatedText.repeat(8) : 'Проверка занимает один рабочий день.' }],
    } },
    trace: { turns: mode === 'recovered' || continued ? [
      { sequence_no: 1, turn_id: `turn-${mode}-1`, speaker_type: 'character', speaker_name: 'Клиент', content_text: 'Когда будет решение?' },
      { sequence_no: 2, turn_id: `turn-${mode}-2`, speaker_type: 'assessee', content_text: 'Сначала уточню зависимость и вернусь с подтверждённым сроком.' },
    ] : [], events: [] },
  };
};

export const createP3BVisualServer = () => http.createServer(async (request, response) => {
  const url = new URL(request.url, 'http://127.0.0.1');
  if (url.pathname === '/p3b-visual') {
    response.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    response.end(`<meta charset="utf-8"><title>P3-B · синтетические состояния</title><h1>P3-B · синтетические состояния</h1><p>Локальный UI preview. Все пользователи, Cycle и диалоги синтетические.</p><ul>${[...modes].map((mode) => `<li><a href="/?screen=interview&p3b=${mode}">${mode}</a></li>`).join('')}</ul><p><a href="/p3b-reset">Сбросить Continue и неизвестный исход</a></p>`);
    return;
  }
  if (url.pathname === '/p3b-reset') {
    states.clear();
    response.writeHead(302, { Location: '/p3b-visual' });
    response.end();
    return;
  }
  if (url.pathname === '/' && url.searchParams.has('p3b')) {
    const mode = url.searchParams.get('p3b');
    if (!modes.has(mode)) return json(response, { detail: 'UNKNOWN_PREVIEW_STATE' }, 404);
    response.setHeader('Set-Cookie', `p3b_preview=${mode}; Path=/; SameSite=Lax`);
  }
  const mode = url.pathname === '/' && modes.has(url.searchParams.get('p3b'))
    ? url.searchParams.get('p3b') : modeFromRequest(request);
  const s = scenario(mode);
  const state = states.get(mode) || { continued: false, uncertain: false, attempts: 0 };
  states.set(mode, state);
  if (mode === 'unknown' && url.pathname === '/') state.uncertain = false;
  if (url.pathname === '/users/version') return json(response, { version: '2.0.86' });
  if (url.pathname === '/users/session/restore') return json(response, { authenticated: true, user, is_admin: false, dashboard: {} });
  if (url.pathname === '/users/8/session-bootstrap') return json(response, { user, is_admin: false, dashboard: {} });
  if (url.pathname === '/users/8/journey-state') return json(response, {
    next_action: 'resume_assessment', profile: { status: 'complete' }, onboarding: { status: 'completed' },
    assessment: { status: 'in_progress', runtime_kind: 'cycle', cycle_id: s.cycleId,
      cycle_session_id: `p3b-session-${mode}`, assessment_situation_id: s.asId },
  });
  if (url.pathname === `/users/assessment/m7/cycles/${s.cycleId}/return-state`) {
    if (state.uncertain) return json(response, { detail: 'TEMPORARY_READ_ERROR' }, 503);
    const blocked = ['pause', 'return', 'unknown'].includes(mode) && !state.continued;
    return json(response, { cycle_id: s.cycleId, collection_status: blocked ? 'paused' : 'active',
      position_no: s.position, current_assessment_situation_id: s.asId,
      current_assessment_situation_status: 'active', allowed_action: blocked ? 'continue_current' : 'active_connection',
      remaining_seconds: s.remaining,
      progress: { completed_positions: s.completed, total_positions: s.total } });
  }
  if (url.pathname === `/users/assessment/m7/cycles/${s.cycleId}/return-continue` && request.method === 'POST') {
    state.attempts += 1;
    if (mode === 'unknown' && (state.attempts === 1 || state.uncertain)) {
      state.uncertain = true;
      request.socket.destroy();
      return;
    }
    state.continued = true;
    return json(response, { cycle_id: s.cycleId, status: 'active', branch: 'continued_current',
      assessment_situation_id: s.asId, remaining_seconds: s.remaining ?? 3600 });
  }
  if (url.pathname === `/users/assessment/cycles/${s.cycleId}/runtime`) return json(response, runtime(mode, state.continued));
  if (url.pathname === `/users/assessment/m7/cycles/${s.cycleId}/presence`) return json(response, {
    cycle_id: s.cycleId, assessment_situation_id: s.asId, heartbeat_interval_seconds: 30, presence_lease_seconds: 120,
  });
  if (url.pathname.startsWith('/users/')) return json(response, { detail: 'UNMOCKED_PREVIEW_API' }, 404);
  const relative = url.pathname === '/' ? 'web/index.html' : url.pathname.replace(/^\/+/, '');
  const filename = path.resolve(root, relative);
  if (!relative.startsWith('web/') || !filename.startsWith(path.join(root, 'web') + path.sep)) {
    return json(response, { detail: 'NOT_FOUND' }, 404);
  }
  try {
    const body = await fs.readFile(filename);
    const contentType = { '.css': 'text/css', '.html': 'text/html', '.js': 'application/javascript',
      '.svg': 'image/svg+xml', '.woff': 'font/woff', '.woff2': 'font/woff2', '.png': 'image/png' }[path.extname(filename)] || 'application/octet-stream';
    response.writeHead(200, { 'Content-Type': contentType });
    response.end(body);
  } catch {
    return json(response, { detail: 'NOT_FOUND' }, 404);
  }
});

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const port = Number(process.env.P3B_VISUAL_PORT || 18769);
  createP3BVisualServer().listen(port, '127.0.0.1', () => {
    process.stdout.write(`P3-B preview: http://127.0.0.1:${port}/p3b-visual\n`);
  });
}
