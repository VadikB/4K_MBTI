// Small extension of the existing synthetic preview: actual checkout product UI,
// shared fixtures, real Python comparison/PDF, no running application or database.
import fs from 'node:fs/promises';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { randomUUID, createHash } from 'node:crypto';
import { pathToFileURL } from 'node:url';
import { startAdminProgramPreview } from './adm-program-ui-preview.mjs';

export async function startReportsPreview({ root = process.cwd(), port = 18972,
  python = process.env.BROWSER_PYTHON || process.env.P4K_PREVIEW_PYTHON || path.join(root, '.venv/bin/python'),
  ttlMs = 15 * 60 * 1000 } = {}) {
  const release = (await fs.readFile(path.join(root, 'web/js/config.js'), 'utf8'))
    .match(/^export const APP_RELEASE = "([^"]+)";$/m)?.[1];
  if (!release) throw new Error('Не удалось прочитать версию приложения из checkout.');
  const children = new Set();
  const render = (command) => new Promise((resolve, reject) => {
    const child = spawn(python, [path.join(root, 'scripts/report_preview_fixture.py')], {
      cwd: root, env: { ...process.env, PYTHON_DOTENV_DISABLED: '1', DB_POOL_MIN_SIZE: '0' },
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    children.add(child);
    const output = [], errors = [];
    const timeout = setTimeout(() => child.kill('SIGKILL'), 30000);
    child.stdout.on('data', (chunk) => output.push(chunk));
    child.stderr.on('data', (chunk) => errors.push(chunk));
    child.on('error', reject);
    child.on('close', (code) => {
      clearTimeout(timeout); children.delete(child);
      if (code === 0) resolve(Buffer.concat(output));
      else reject(new Error('Локальный Python/PDF renderer недоступен: ' + Buffer.concat(errors).toString().slice(-1800)));
    });
    child.stdin.end(JSON.stringify(command));
  });
  const payload = JSON.parse((await render({ operation: 'payload' })).toString());
  const reports = payload.reports;
  const byId = new Map(Object.entries(reports).map(([name, value]) => [value.id, name]));
  const sessions = new Map();
  const title = { P01: 'Полный отчёт', P02: 'Четыре исхода и пропуски', P03: 'Две сопоставимые оценки',
    P04: 'Сопоставимые частичные показатели', P05: 'Ограничения и разные роли', P06: 'Ошибка чтения и отказ PDF' };
  const address = (name, previous = '') => '/?' + new URLSearchParams({ screen: 'report',
    cycle_id: reports[name].cycle_id, report_id: reports[name].id,
    ...(previous ? { previous_report_id: reports[previous].id, report_view: 'comparison' } : {}) });
  const html = (body) => `<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Локальный просмотр отчётов</title><style>@font-face{font-family:Onest;src:url('/web/assets/fonts/onest/Onest-Variable.woff')}*{box-sizing:border-box}body{margin:0;font:15px/1.5 Onest,system-ui;background:#f7f7f7;color:#222c30}header,main{padding:16px;max-width:1160px;margin:auto}a,button{color:#007d89}nav{display:flex;flex-wrap:wrap;gap:12px}li{margin:12px 0}button{font:inherit;padding:8px;border:1px solid #cbd5e1;border-radius:8px;background:white;cursor:pointer}iframe{display:block;width:100%;height:calc(100vh - 180px);min-height:540px;border:0;background:white}label{display:inline-flex;gap:6px;margin:6px}p{margin:6px 0}code{overflow-wrap:anywhere}</style>${body}</html>`;
  const adapter = async ({ request, response, url, identity }) => {
    // No remote assets/services, even if the product later gains an external URL.
    response.setHeader('Content-Security-Policy', "default-src 'self' data: blob:; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'self'");
    response.setHeader('Cache-Control', 'no-store');
    const json = (body, code = 200) => { response.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8' }); response.end(JSON.stringify(body)); return true; };
    const document = (body) => { response.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' }); response.end(body); return true; };
    const id = request.headers.cookie?.match(/(?:^|; )reports_preview=([^;]+)/)?.[1];
    let session = sessions.get(id);
    if (url.pathname === '/__reports/identity') return json({ ...identity,
      command: 'npm run preview:reports', ttl_minutes: ttlMs / 60000, database: false, llm: 0, mail: 0,
      fixture_source: payload.fixture.source, fixture_source_sha256: payload.fixture.source_sha256 });
    if (url.pathname === '/__reports/' || (url.pathname === '/' && !url.searchParams.has('screen'))) {
      return document(html(`<main><h1>Локальный просмотр · вымышленные результаты</h1><p>Настоящие экраны этого checkout. БД, LLM и почта не используются. Ctrl+C — остановить; TTL 15 минут.</p><p>Checkout SHA: <code>${identity.source_head_sha}</code>. Программа и даты сохранены в примерах.</p><ul>${Object.entries(title).map(([key, value]) => `<li><a href="/__reports/${key}">${key} · ${value}</a></li>`).join('')}</ul><p>А: «Ориентация и проектирование коммуникации». Б: «Передача смысла». В: «Слушание, реконструкция и верификация смысла другого».</p><p>P03: +0,50 / 0 / −0,25. P04: 1,50 → 1,75, разность +0,25. Эти числа заданы для проверки интерфейса.</p></main>`));
    }
    const example = url.pathname.match(/^\/__reports\/(P0[1-6])$/)?.[1];
    if (example) {
      const sessionId = randomUUID();
      session = { example, readFailure: example === 'P06', pdfFailure: example === 'P06' };
      sessions.set(sessionId, session);
      response.setHeader('Set-Cookie', `reports_preview=${sessionId}; Path=/; SameSite=Strict; HttpOnly`);
      const config = payload.fixture.examples[example];
      return document(html(`<header><nav><a href="/__reports/">Все примеры P01–P06</a><strong>Локальный просмотр · вымышленные результаты · ${example}</strong></nav><p>${title[example]}</p><nav><a target="report-product" href="/?screen=reports">История оценок</a><a target="report-product" href="/?screen=admin-reports">Список администратора</a>${example === 'P05' ? `<a target="report-product" href="${address(config.current, config.alternative)}">Разные роли</a>` : ''}${example === 'P06' ? `<a target="report-product" href="${address('error-b')}">Открыть отчёт B</a><label><input id="read-failure" type="checkbox" checked>Ошибка чтения B</label><label><input id="pdf-failure" type="checkbox" checked>Отказ PDF</label><button id="success" type="button">Успешный повтор</button><span id="control-status" role="status"></span>` : ''}</nav></header><iframe name="report-product" title="Настоящий экран отчёта" src="${address(config.current, config.previous)}"></iframe>${example === 'P06' ? `<script>const update=async()=>{const r=await fetch('/__reports/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({readFailure:document.getElementById('read-failure').checked,pdfFailure:document.getElementById('pdf-failure').checked})});document.getElementById('control-status').textContent=r.ok?'Режим обновлён. Нажмите повтор на экране.':'Не удалось изменить режим'};for(const id of ['read-failure','pdf-failure'])document.getElementById(id).onchange=update;document.getElementById('success').onclick=()=>{document.getElementById('read-failure').checked=false;document.getElementById('pdf-failure').checked=false;update()};</script>` : ''}`));
    }
    if (url.pathname === '/__reports/control') {
      if (!session || request.method !== 'POST' || request.headers.origin !== `http://${request.headers.host}`) return json({ detail: 'Недопустимое управление локальным примером.' }, 403);
      let body = ''; for await (const chunk of request) { body += chunk; if (body.length > 1024) return json({}, 413); }
      try { const value = JSON.parse(body); session.readFailure = value.readFailure === true; session.pdfFailure = value.pdfFailure === true; }
      catch { return json({}, 400); }
      return json({ ...session });
    }
    if (url.pathname === '/' && url.searchParams.has('screen')) {
      if (session) session.admin = url.searchParams.get('screen').startsWith('admin');
      return document(await fs.readFile(path.join(root, 'web/index.html'), 'utf8'));
    }
    if (!url.pathname.startsWith('/users/')) return false;
    if (!session) return json({ authenticated: false }, 401);
    const config = payload.fixture.examples[session.example];
    const names = [...new Set([config.current, config.previous, config.alternative, config.failed].filter(Boolean))];
    const history = names.map((name) => ({ ...reports[name], report_id: reports[name].id, status: 'report_ready' }));
    const user = { id: 18, email: 'participant@example.test', full_name: 'Вымышленный участник' };
    const admin = session.admin === true;
    if (url.pathname === '/users/version') return json({ version: release });
    if (url.pathname === '/users/session/restore' || url.pathname === '/users/18/session-bootstrap') {
      return json({ authenticated: true, exists: true, user, is_admin: admin,
        dashboard: { user, active_assessment: null, current_assessments: [], completed_assessments: history },
        ...(admin ? { admin_dashboard: { is_superadmin: false, metrics: [], insights: [], activity_series: [], competency_average: [] } } : {}),
        active_area: admin ? 'management' : 'assessment' });
    }
    if (url.pathname === '/users/18/journey-state') return json({ next_action: 'show_dashboard' });
    if (url.pathname === '/users/assessment/m8/history') return json({ cycles: history });
    if (url.pathname === '/users/admin/m8-access/reports') return json({ items: names.map((name) => ({ ...reports[name], report_id: reports[name].id,
      full_name: user.full_name, organization_name: 'Вымышленная организация' })), total: names.length, page: 1,
      organizations: [{ id: 1, name: 'Вымышленная организация' }], programs: [...new Set(history.map((item) => item.program_name))] });
    const latest = url.pathname.match(/\/cycles\/([^/]+)\/reports\/latest$/);
    if (latest) {
      const report = Object.values(reports).find((item) => item.cycle_id === latest[1]);
      return report ? json(report) : json({}, 404);
    }
    const match = url.pathname.match(/\/(?:m8|m8-access)\/reports\/([^/]+)(?:\/(comparison(?:\.pdf)?|pdf))?$/);
    if (match) {
      const name = byId.get(match[1]);
      if (!name || !names.includes(name)) return json({ detail: 'Пример не найден.' }, 404);
      if (!match[2]) return name === 'error-b' && session.readFailure
        ? json({ detail: 'Не удалось открыть результат.' }, 503) : json(reports[name]);
      if (match[2].includes('pdf') && session.pdfFailure) return json({ detail: 'PDF временно недоступен. Повторите скачивание.' }, 503);
      const previous = byId.get(url.searchParams.get('previous_report_id'));
      if (match[2].startsWith('comparison') && (!previous || !names.includes(previous)
        || reports[previous].collection_closed_at >= reports[name].collection_closed_at)) return json({ detail: 'Пара примеров недоступна.' }, 403);
      try {
        const bytes = await render({ operation: match[2] === 'comparison.pdf' ? 'comparison_pdf' : match[2] === 'pdf' ? 'pdf' : 'compare', current: name, previous });
        if (match[2] === 'comparison') { response.writeHead(200, { 'Content-Type': 'application/json' }); response.end(bytes); }
        else { response.writeHead(200, { 'Content-Type': 'application/pdf', 'Content-Disposition': `attachment; filename="4k-${name}.pdf"` }); response.end(bytes); }
        return true;
      } catch (error) { return json({ detail: error.message }, 503); }
    }
    return json({ detail: 'Этот запрос не входит в локальный просмотр отчётов.' }, 404);
  };
  const preview = await startAdminProgramPreview({ root, port, adapter });
  for (const name of ['Api/m8_report_comparison.py', 'Api/m8_pdf_radar.py', 'Api/pdf_templates/m8_report_comparison_v3.typ',
    'web/js/screens/report.js', 'web/js/utils/report-comparison.js', 'web/styles/screens/report.css',
    'web/styles/screens/reports.css', 'web/styles/tokens.css', 'scripts/reports-ui-preview.mjs',
    'scripts/report_preview_fixture.py', 'tests/fixtures/m8_report_preview.json']) {
    preview.identity.source_sha256[name] = createHash('sha256').update(await fs.readFile(path.join(root, name))).digest('hex');
  }
  // 0 chooses an available port, without terminating anything already listening.
  const actualPort = preview.server.address().port;
  const close = async () => {
    clearTimeout(ttl);
    for (const child of children) child.kill('SIGTERM');
    preview.server.closeAllConnections();
    await preview.close();
  };
  const ttl = setTimeout(() => void close(), ttlMs);
  return { ...preview, base: `http://127.0.0.1:${actualPort}`, close, payload };
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  try {
    const index = process.argv.indexOf('--port');
    const preview = await startReportsPreview({ port: Number(index >= 0 ? process.argv[index + 1] : process.env.P4K_REPORT_PREVIEW_PORT || 18972) });
    console.log(`Локальный просмотр · вымышленные результаты\nОткройте ${preview.base}/__reports/\nCheckout SHA: ${preview.identity.source_head_sha}\nОстановить: Ctrl+C. TTL: 15 минут.`);
    for (const signal of ['SIGINT', 'SIGTERM']) process.once(signal, async () => { await preview.close(); process.exit(0); });
  } catch (error) {
    console.error(error.message);
    console.error('Для Python/PDF нужны .venv и pip install -r requirements.txt (typst>=0.14.8). Другой Python: P4K_PREVIEW_PYTHON. Если порт занят: npm run preview:reports -- --port 18974.');
    process.exitCode = 1;
  }
}
