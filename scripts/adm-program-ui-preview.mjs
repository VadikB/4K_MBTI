// Local synthetic HTTP gallery. Serves the real product HTML/dist; no DB, mail,
// provider, TEST access or replacement DOM. Never install as a runtime service.
import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import { createHash, randomUUID } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';

export async function startAdminProgramPreview({ root = process.cwd(), port = 18944 } = {}) {
  const sourcePaths = ['web/index.html', 'web/js/screens/admin/organizations.js', 'web/js/wiring.js',
    'web/js/entries/admin-organizations.js', 'web/styles/screens/admin-organizations.css',
    'web/js/config.js', ...(await fs.readdir(path.join(root, 'web/dist'))).map((name) => 'web/dist/' + name)];
  const identity = { scope: 'local_synthetic_http', source_head_sha: spawnSync('git', ['rev-parse', 'HEAD'],
    { cwd: root, encoding: 'utf8' }).stdout.trim(), provider_operations: 0, database: false,
    source_sha256: Object.fromEntries(await Promise.all(sourcePaths.map(async (name) => [name,
      createHash('sha256').update(await fs.readFile(path.join(root, name))).digest('hex')]))),
    process_run_id: randomUUID() };
  const sessions = new Map();
  const program = (id = 11) => ({ organization_id: 3, program_definition_id: id,
    program_name: 'Синтетическая программа оценки · подробные сведения о профессиональной работе',
    program_version: 'synthetic-1.' + id, assignment_ref: 'synthetic-pilot-' + id,
    roles: [{ version_id: 7, code: 'specialist', name: 'Специалист' }],
    role_capabilities: [{ version_id: 7, code: 'specialist', name: 'Специалист', is_available: true }] });
  const requests = [];
  const server = http.createServer(async (request, response) => {
    const url = new URL(request.url, 'http://127.0.0.1:' + port);
    const json = (body, status = 200) => { response.writeHead(status, { 'Content-Type': 'application/json' }); response.end(JSON.stringify(body)); };
    if (url.pathname === '/__preview/identity') return json(identity);
    if (url.pathname === '/__preview/requests') return json(requests);
    const match = url.pathname.match(/^\/demo\/(admin|superadmin)\/(absent|unknown|confirmed)\/$/);
    if (match) {
      const id = randomUUID();
      sessions.set(id, { role: match[1], status: match[2], linked: 11, revisions: [], name: 'Синтетическая ИТ-организация' });
      response.setHeader('Set-Cookie', 'adm_preview=' + id + '; Path=/; SameSite=Strict; HttpOnly');
    }
    const id = request.headers.cookie?.match(/(?:^|; )adm_preview=([^;]+)/)?.[1];
    const session = sessions.get(id);
    if (url.pathname.startsWith('/users/')) {
      requests.push({ method: request.method, path: url.pathname, synthetic: true });
      if (url.pathname === '/users/version') return json({ version: '2.0.87 · LOCAL SYNTHETIC' });
      if (!session) return json({ authenticated: false });
      const isSuperadmin = session.role === 'superadmin';
      const dashboard = { is_superadmin: isSuperadmin, metrics: [], insights: [], activity_series: [], competency_average: [] };
      const connection = () => session.status === 'absent' ? null : program(session.linked);
      const organization = () => ({ id: 3, code: 'synthetic-adm-program', name: session.name,
        is_active: true, members_count: 1, reports_count: 0, domains: [],
        admins: [{ user_id: 18, email: 'admin@example.test', full_name: 'Синтетический администратор' }],
        members: [{ user_id: 28, email: 'member@example.test', full_name: 'Синтетический участник',
          role_description: 'Специалист', assessment_assignments: [] }],
        ...(session.status === 'unknown' ? {} : { assessment_program: connection() }) });
      if (url.pathname === '/users/session/restore' || url.pathname === '/users/18/session-bootstrap') return json({ authenticated: true, exists: true,
        user: { id: 18, email: 'admin@example.test', full_name: isSuperadmin ? 'Синтетический суперадминистратор' : 'Синтетический администратор' },
        is_admin: true, admin_dashboard: dashboard });
      if (url.pathname === '/users/admin/dashboard') return json(dashboard);
      if (url.pathname === '/users/admin/organizations') return json({ is_superadmin: isSuperadmin,
        items: [organization()], assessment_programs: [11, 12].map((n) => ({ id: n, name: program(n).program_name, version: program(n).program_version })) });
      if (url.pathname === '/users/admin/organizations/3/questionnaire') return json({ items: session.revisions.filter((item) => item.status === 'confirmed') });
      if (url.pathname === '/users/admin/organizations/3/assessment-program') {
        if (request.method === 'PUT') {
          if (!isSuperadmin) return json({ detail: 'Synthetic superadmin-only command' }, 403);
          const body = await readBody(request);
          session.linked = body.program_definition_id;
        }
        session.status = 'confirmed';
        return json({ connection: connection() });
      }
      if (url.pathname === '/users/admin/organizations/3' && request.method === 'PATCH') {
        const body = await readBody(request); session.name = body.name;
        return json({ is_superadmin: isSuperadmin, items: [organization()] });
      }
      // The gallery prepares connection states only. The accepted positive
      // questionnaire path is verified separately against actual HTTP/owned PG.
      return json({ detail: 'Локальный просмотр состояний. Для preview/confirm используется отдельный actual HTTP/PG test.' }, 409);
    }
    const appReload = url.pathname === '/' && session && url.searchParams.has('screen');
    if ((url.pathname === '/' && !appReload) || url.pathname === '/adm-program-ui/') {
      response.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      response.end('<!doctype html><html lang="ru"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ADM PROGRAM · локальный просмотр</title><body style="font:18px system-ui;max-width:760px;margin:40px auto;padding:20px"><h1>Формы организации</h1><p>Локальные синтетические состояния на фактическом UI. БД, TEST, LLM и почта не используются.</p><p>После входа откройте «Организации», затем «Данные организации» и «Анкета». Поля и автор доступны для набора черновика; отсутствие программы не блокирует карточку.</p>' +
        ['admin', 'superadmin'].map((role) => '<h2>' + (role === 'admin' ? 'Администратор' : 'Суперадминистратор') + '</h2><ul>' +
          ['absent', 'unknown', 'confirmed'].map((state) => '<li><a href="/demo/' + role + '/' + state + '/">' +
            ({ absent: 'Программы нет', unknown: 'Подключение неизвестно · GET-проверка', confirmed: 'Подтверждённая программа' })[state] + '</a></li>').join('') + '</ul>').join('') +
        '<p>Для unknown кнопка «Проверить состояние подключения» выполняет синтетический GET и открывает подтверждённую программу. Полный manual/CSV→confirm проверен отдельным runner.</p></body></html>');
      return;
    }
    if (url.pathname === '/app-config.js') { response.setHeader('Content-Type', 'application/javascript'); response.end('window.__APP_CONFIG__ = {};'); return; }
    const relative = match || appReload ? 'web/index.html' : url.pathname.replace(/^\//, '');
    if ((!match && !appReload && !relative.startsWith('web/')) || relative.includes('..')) { response.writeHead(404); response.end(); return; }
    try {
      const bytes = await fs.readFile(path.join(root, relative));
      response.setHeader('Content-Type', { '.html': 'text/html; charset=utf-8', '.js': 'application/javascript',
        '.css': 'text/css', '.svg': 'image/svg+xml', '.woff': 'font/woff', '.woff2': 'font/woff2' }[path.extname(relative)] || 'application/octet-stream');
      response.end(bytes);
    } catch { response.writeHead(404); response.end(); }
  });
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(port, '127.0.0.1', resolve); });
  return { server, identity, requests, base: 'http://127.0.0.1:' + port, close: () => new Promise((resolve) => server.close(resolve)) };
}
async function readBody(request) {
  let body = ''; for await (const chunk of request) body += chunk;
  return JSON.parse(body || '{}');
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const preview = await startAdminProgramPreview({ port: Number(process.env.P4K_ADM_PREVIEW_PORT || 18944) });
  console.log(JSON.stringify({ url: preview.base + '/adm-program-ui/', scope: preview.identity.scope, source_head_sha: preview.identity.source_head_sha }));
  for (const signal of ['SIGINT', 'SIGTERM']) process.once(signal, async () => { await preview.close(); process.exit(0); });
}
