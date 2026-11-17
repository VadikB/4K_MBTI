// Actual bundled UI + synthetic HTTP and controlled clock, no DB/provider/mail.
import { test, expect } from '@playwright/test';
import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import { draftSlot } from '../../web/js/answer-drafts.js';

let server, base;
const evidence = process.env.POSTW05_EVIDENCE || 'docs/evc/tasks/p4k-postw02-05/evidence/browser';
const reference = process.env.POSTW02_REFERENCE;
test.beforeAll(async () => {
  await fs.mkdir(evidence, { recursive: true });
  server = http.createServer(async (req, res) => {
    try {
      const pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
      const file = pathname.startsWith('/reference/') && reference
        ? path.join(reference, 'dist', pathname.slice('/reference/'.length))
        : path.join(process.cwd(), pathname === '/' ? 'web/index.html' : pathname);
      res.setHeader('Content-Type', { '.html': 'text/html', '.css': 'text/css', '.js': 'application/javascript',
        '.mjs': 'application/javascript', '.svg': 'image/svg+xml', '.woff': 'font/woff' }[path.extname(file)] || 'application/octet-stream');
      res.end(await fs.readFile(file));
    } catch { res.statusCode = 404; res.end('missing'); }
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  base = `http://127.0.0.1:${server.address().port}`;
});
test.afterAll(async () => {
  const port = server?.address()?.port;
  if (server?.listening) await new Promise((resolve) => server.close(resolve));
  await fs.writeFile(path.join(evidence, 'cleanup.json'), JSON.stringify({ port, listening: server?.listening, db: null, llm: 0, mail: 0 }));
});

async function fixture(page, shared = null) {
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

async function captureDraft(page, scene, width) {
  // Controlled-clock tests must also settle the real CSS transition before measuring colors.
  await page.clock.runFor(250);
  await expect(page.locator('#interview-submit-button')).toHaveCSS('background-color', scene === 'conflict' ? 'rgb(214, 226, 229)' : 'rgb(24, 184, 198)');
  await page.evaluate(async () => { await document.fonts.ready; await Promise.all(document.getAnimations().filter(a => a.effect?.getTiming().iterations !== Infinity).map(a => a.finished.catch(() => {}))); });
  const ui = await page.evaluate(() => {
    const field = document.querySelector('#interview-textarea'), button = document.querySelector('#interview-submit-button');
    const rect = el => { const r = el.getBoundingClientRect(); return { x:r.x, y:r.y, width:r.width, height:r.height, bottom:r.bottom }; };
    const css = el => { const s = getComputedStyle(el); return Object.fromEntries(
      ['backgroundColor','color','opacity','borderRadius','borderColor','outlineWidth','outlineColor','outlineOffset','resize','padding','fontSize','lineHeight','minHeight','maxHeight'].map(k => [k,s[k]])); };
    return { width: innerWidth, scrollWidth: document.documentElement.scrollWidth, field: rect(field), button: rect(button),
      fieldStyle: css(field), buttonStyle: css(button), disabled: button.disabled, text: field.value,
      status: document.querySelector('#interview-draft-status').textContent,
      timer: css(document.querySelector('#interview-timer-badge')),
      scenario: rect(document.querySelector('.product-situation-message')),
      scenarioTitle: css(document.querySelector('.product-situation-title')),
      scenarioBody: css(document.querySelector('.product-situation-message .interview-structured-block-body')),
      actions: [...document.querySelectorAll('#interview-draft-actions button')].map(b => ({text:b.textContent,rect:rect(b),style:css(b)})) };
  });
  expect(ui.scrollWidth).toBeLessThanOrEqual(width);
  expect(ui.disabled).toBe(scene === 'conflict');
  expect(ui.buttonStyle.opacity).toBe('1');
  expect(ui.buttonStyle.backgroundColor).toBe(scene === 'conflict' ? 'rgb(214, 226, 229)' : 'rgb(24, 184, 198)');
  expect(ui.buttonStyle.color).toBe(scene === 'conflict' ? 'rgb(104, 119, 124)' : 'rgb(34, 44, 48)');
  expect(ui.fieldStyle).toMatchObject({borderRadius:'8px',resize:'none',padding:'12px',fontSize:'16px',lineHeight:'24px',minHeight:'48px',maxHeight:'120px'});
  expect(ui.field.height).toBe(96);
  expect(ui.timer).toMatchObject({fontSize:'24px',lineHeight:'32px'});
  expect(ui.scenarioBody).toMatchObject({fontSize:'16px',lineHeight:'24px'});
  expect(ui.scenarioTitle).toMatchObject({fontSize:width === 1440?'20px':'18px',lineHeight:width === 1440?'28px':'26px'});
  if (width === 1440) {
    expect(ui.button.width).toBe(200); expect(Math.abs(ui.button.bottom-ui.field.bottom)).toBeLessThan(1);
    expect(ui.scenario.width).toBeCloseTo(880, 1);
  } else { expect(ui.button.width).toBe(ui.field.width); expect(ui.button.y).toBeGreaterThan(ui.field.bottom); }
  for (const action of ui.actions) {
    expect(action.rect.height).toBeGreaterThanOrEqual(44); expect(action.style.color).toBe('rgb(0, 125, 137)');
  }
  await fs.writeFile(path.join(evidence, `${scene}-${width}.json`), JSON.stringify({...ui,
    disabledReason:scene === 'conflict'?'Явный выбор редакции ещё не выполнен':'Active runtime; нет pending/Continue/closed; saved/offline draft сам по себе не блокирует отправку'},null,2));
  await page.screenshot({path:path.join(evidence, `${scene}-${width}.png`),fullPage:true});
  return ui;
}

for (const width of [1440, 390]) test(`05A/B/C/D/F durable draft browser ${width}`, async ({ page, context, browser }) => {
  await page.setViewportSize({ width, height: width === 1440 ? 1000 : 844 });
  await page.clock.install({ time: new Date('2026-11-17T12:00:00Z') });
  const errors = []; page.on('pageerror', e => errors.push(e.message));
  const run = await fixture(page);
  await page.goto(`${base}/?screen=interview`);
  const field = page.locator('#interview-textarea'), status = page.locator('#interview-draft-status');
  await expect(field).toBeEnabled();
  const raw = '  Черновик ответа\nВторая строка\n  ';
  await field.fill(raw); await page.clock.runFor(800);
  await expect(status).toHaveText('Черновик сохранён');
  expect(run.model.trace.turns).toHaveLength(2);
  const savedUI = await captureDraft(page, 'saved', width);

  // A completely separate browser context has only the server revision.
  const clean = await browser.newContext({ viewport: { width, height: 844 } });
  const cleanPage = await clean.newPage(); await fixture(cleanPage, run);
  await cleanPage.goto(`${base}/?screen=interview`);
  await expect(cleanPage.locator('#interview-textarea')).toHaveValue(raw);
  await expect(cleanPage.locator('#interview-draft-status')).toContainText('Ответ ещё не отправлен');
  await clean.close();

  // Close the actual tab before the debounce; new tab in the same browser
  // receives the raw durable local buffer and then synchronizes it.
  const latest = raw + 'Сразу перед закрытием';
  await field.fill(latest); await page.close();
  const next = await context.newPage(); await next.setViewportSize({ width, height: width === 1440 ? 1000 : 844 });
  await next.clock.install({ time: new Date('2026-11-17T12:00:01Z') });
  await fixture(next, run); await next.goto(`${base}/?screen=interview`);
  await expect(next.locator('#interview-textarea')).toHaveValue(latest);
  await expect(next.locator('#interview-draft-status')).toHaveText('Черновик сохранён');

  run.draftOffline = true;
  await next.locator('#interview-textarea').fill(latest + '\nБез связи'); await next.clock.runFor(800);
  await expect(next.locator('#interview-draft-status')).toContainText('на этом устройстве');
  const offlineUI = await captureDraft(next, 'offline', width);
  expect(offlineUI.field.width).toBe(savedUI.field.width); expect(offlineUI.button.width).toBe(savedUI.button.width);
  run.draftOffline = false; await next.evaluate(() => window.dispatchEvent(new Event('online')));
  await expect(next.locator('#interview-draft-status')).toHaveText('Черновик сохранён');

  // Server change from another device creates an explicit conflict.
  const saved = run.drafts[draftSlot(run.model)]; saved.version++; saved.revision = 'other-device'; saved.text = 'Другая редакция';
  await next.locator('#interview-textarea').fill('Мой текст при конфликте'); await next.clock.runFor(800);
  await expect(next.locator('#interview-draft-status')).toContainText('другой вкладке');
  await expect(next.locator('#interview-textarea')).toHaveValue('Мой текст при конфликте');
  const conflictUI = await captureDraft(next, 'conflict', width);
  expect(conflictUI.field.width).toBe(savedUI.field.width); expect(conflictUI.button.width).toBe(savedUI.button.width);
  const postsBeforeChoice = run.calls.filter(c => c.url.endsWith('/turns') && c.method === 'POST').length;
  await next.clock.fastForward(1500); // A runtime poll must not re-enable unresolved conflict.
  await expect(next.locator('#interview-submit-button')).toBeDisabled();
  expect(run.calls.filter(c => c.url.endsWith('/turns') && c.method === 'POST')).toHaveLength(postsBeforeChoice);
  await next.getByRole('button', { name: 'Оставить текст из этой вкладки', exact: true }).click();
  await expect(next.locator('#interview-draft-status')).toHaveText('Черновик сохранён');

  expect(run.calls.filter(c => c.url.endsWith('/turns') && c.method === 'POST')).toHaveLength(postsBeforeChoice);
  await expect(next.locator('#interview-submit-button')).toBeEnabled();

  // The other explicit choice adopts the remote version without posting an answer.
  saved.version++; saved.revision = 'other-choice'; saved.text = 'Выбранный сохранённый вариант';
  await next.locator('#interview-textarea').fill('Локальная редакция до выбора'); await next.clock.runFor(800);
  await expect(next.locator('#interview-textarea')).toHaveValue('Локальная редакция до выбора');
  await next.getByRole('button', {name:'Использовать другой сохранённый вариант',exact:true}).click();
  await expect(next.locator('#interview-textarea')).toHaveValue('Выбранный сохранённый вариант');
  expect(run.calls.filter(c => c.url.endsWith('/turns') && c.method === 'POST')).toHaveLength(postsBeforeChoice);
  await next.locator('#interview-textarea').fill('Мой текст при конфликте'); await next.clock.runFor(800);

  // A real second tab uses the shared durable buffer; the first keeps its text
  // and requires an explicit choice when it receives the storage event.
  const sibling = await context.newPage(); await fixture(sibling, run);
  await sibling.goto(`${base}/?screen=interview`);
  await expect(sibling.locator('#interview-textarea')).toHaveValue('Мой текст при конфликте');
  await sibling.locator('#interview-textarea').fill('Редакция из второй вкладки');
  await expect(next.locator('#interview-draft-status')).toContainText('другой вкладке');
  await expect(next.locator('#interview-textarea')).toHaveValue('Мой текст при конфликте');
  await sibling.close();
  await next.getByRole('button', { name: 'Оставить текст из этой вкладки', exact: true }).click();
  await expect(next.locator('#interview-draft-status')).toHaveText('Черновик сохранён');

  // Lost accepted response + tab close retains the original request/Turn ID.
  run.dropAnswer = true;
  await next.locator('#interview-submit-button').click();
  await expect.poll(() => Boolean(run.receipt)).toBe(true);
  await next.close();
  const recovered = await context.newPage(); await recovered.setViewportSize({ width, height: width === 1440 ? 1000 : 844 });
  await fixture(recovered, run);
  await recovered.goto(`${base}/?screen=interview`);
  await expect(recovered.locator('#interview-textarea')).toHaveValue('');
  await expect.poll(() => run.calls.filter(c => c.url.endsWith('/answer-status')).length).toBeGreaterThan(0);
  expect(run.calls.filter(c => c.url.endsWith('/turns') && c.method === 'POST')).toHaveLength(1);
  expect(run.unexpected).toEqual([]); expect(errors).toEqual([]);
  const geometry = await recovered.evaluate(() => ({ width: innerWidth, scrollWidth: document.documentElement.scrollWidth }));
  expect(geometry.scrollWidth).toBeLessThanOrEqual(width);
  await fs.writeFile(path.join(evidence, `receipt-${width}.json`), JSON.stringify({ geometry, turns: run.model.trace.turns.length,
    posts: run.calls.filter(c => c.url.endsWith('/turns') && c.method === 'POST').length, errors }));
});


test('UI B/D: focus, long text, reading position, 320px and reduced keyboard viewport', async ({page}) => {
  await page.setViewportSize({width:390,height:844});
  await page.clock.install({time:new Date('2026-11-17T12:00:00Z')});
  const run = await fixture(page);
  run.model.current_situation.participant_payload.introduction = 'Длинный синтетический материал для прокрутки. '.repeat(80);
  await page.goto(`${base}/?screen=interview`);
  const field=page.locator('#interview-textarea'), status=page.locator('#interview-draft-status');
  await expect(field).toBeEnabled();
  const style = () => field.evaluate(n => {const s=getComputedStyle(n); return {radius:s.borderRadius,border:s.borderColor,
    outline:s.outlineWidth,outlineColor:s.outlineColor,offset:s.outlineOffset,resize:s.resize};});
  await page.locator('#interview-case-badge').click(); await page.clock.runFor(250);
  const blur=await style(); expect(blur).toMatchObject({radius:'8px',outline:'0px',border:'rgba(0, 0, 0, 0)',resize:'none'});
  await field.click(); await page.clock.runFor(250);
  const click=await style(); expect(click).toMatchObject({outline:'1px',outlineColor:'rgb(0, 125, 137)',border:'rgb(0, 125, 137)',offset:'0px'});
  await page.keyboard.press('Tab'); await expect(page.locator('#interview-submit-button')).toBeFocused();
  await page.keyboard.press('Shift+Tab'); await expect(field).toBeFocused();
  const tab=await style(); expect(tab).toEqual(click);
  const send=page.locator('#interview-submit-button');
  await send.hover(); await expect(send).toHaveCSS('background-color','rgb(16, 158, 171)');
  await page.mouse.down(); await expect(send).toHaveCSS('background-color','rgb(12, 133, 145)');
  await page.mouse.move(0,0); await page.mouse.up();
  await field.focus();
  const longText=Array.from({length:100},(_,i)=>`Строка ${i}: весь длинный ответ доступен для редактирования.`).join('\n');
  await field.fill(longText);
  const before=await field.evaluate(n => {window.__draftInput=n;n.setSelectionRange(450,480,'backward');n.scrollTop=240;
    return {start:n.selectionStart,end:n.selectionEnd,direction:n.selectionDirection,top:n.scrollTop};});
  await page.clock.runFor(800); await expect(status).toHaveText('Черновик сохранён');
  const after=await field.evaluate(n=>({start:n.selectionStart,end:n.selectionEnd,direction:n.selectionDirection,top:n.scrollTop,
    same:n===window.__draftInput,focus:document.activeElement===n,text:n.value,scrollHeight:n.scrollHeight,height:n.clientHeight}));
  expect(after).toMatchObject({...before,same:true,focus:true,text:longText}); expect(after.scrollHeight).toBeGreaterThan(after.height);
  await field.evaluate(n=>{n.scrollTop=n.scrollHeight;n.setSelectionRange(n.value.length,n.value.length);});
  expect(await field.evaluate(n=>n.scrollTop+n.clientHeight >= n.scrollHeight-1)).toBe(true);
  await page.reload(); await expect(field).toHaveValue(longText);
  await expect(status).toContainText('Ответ ещё не отправлен');
  const area=page.locator('#interview-scroll-area'), down=page.locator('#interview-messages-scroll');
  await area.evaluate(n=>n.scrollTo({top:0,behavior:'instant'}));
  await expect(down).toBeVisible();
  const reading=await area.evaluate(n=>n.scrollTop);
  await field.fill(longText+'\nПоследняя строка'); await page.clock.runFor(800);
  await expect(status).toHaveText('Черновик сохранён'); expect(await area.evaluate(n=>n.scrollTop)).toBe(reading);
  await down.click(); await page.clock.runFor(600);
  await expect(down).toBeHidden();
  await expect.poll(() => area.evaluate(n => n.scrollHeight-n.scrollTop-n.clientHeight)).toBeLessThanOrEqual(1);
  await expect.poll(() => area.evaluate(n => getComputedStyle(n.closest('.interview-messages-shell'),'::after').opacity)).toBe('0');
  const last=page.locator('#interview-messages .interview-message').last();
  const end=await last.evaluate(n=>{const area=document.querySelector('#interview-scroll-area'), r=n.getBoundingClientRect(), a=area.getBoundingClientRect();
    return {bottom:r.bottom,areaBottom:a.bottom,fade:getComputedStyle(area.closest('.interview-messages-shell'),'::after').opacity};});
  expect(end.bottom).toBeLessThanOrEqual(end.areaBottom+1); expect(end.fade).toBe('0');
  await page.screenshot({path:path.join(evidence,'latest-turn-390.png'),fullPage:true});
  const layouts=[];
  // Reduced viewport emulates the space left by a keyboard, not a physical OS keyboard.
  for (const viewport of [{width:320,height:700},{width:390,height:390},{width:320,height:360}]) {
    await page.setViewportSize(viewport); await field.focus();
    for (const selector of ['#interview-textarea','#interview-draft-status','#interview-submit-button']) {
      const control=page.locator(selector);await control.scrollIntoViewIfNeeded();
      const b=await control.boundingBox();expect(b.x).toBeGreaterThanOrEqual(0);expect(b.x+b.width).toBeLessThanOrEqual(viewport.width);
      expect(b.y).toBeGreaterThanOrEqual(0);expect(b.y+b.height).toBeLessThanOrEqual(viewport.height+1);
    }
    expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(viewport.width);
    await expect(field).toHaveValue(longText+'\nПоследняя строка');
    layouts.push(viewport);await page.screenshot({path:path.join(evidence,`keyboard-emulated-${viewport.width}-${viewport.height}.png`),fullPage:true});
  }
  const other=run.drafts[draftSlot(run.model)];other.version++;other.revision='narrow-conflict';other.text='Вариант другого устройства';
  await field.fill('Локальная редакция на 320');await page.clock.runFor(800);
  await expect(status).toContainText('Выберите, с каким текстом');
  const blocked=page.locator('#interview-submit-button');
  await expect(blocked).toBeDisabled(); await blocked.hover();
  await expect(blocked).toHaveCSS('background-color','rgb(214, 226, 229)');
  await page.mouse.down(); await expect(blocked).toHaveCSS('background-color','rgb(214, 226, 229)');
  await page.mouse.up();
  for(const choice of await page.locator('#interview-draft-actions button').all()) {
    await choice.scrollIntoViewIfNeeded();const r=await choice.boundingBox();
    expect(r.x).toBeGreaterThanOrEqual(0);expect(r.x+r.width).toBeLessThanOrEqual(320);
    expect(r.y+r.height).toBeLessThanOrEqual(361);
  }
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(320);
  await fs.writeFile(path.join(evidence,'interaction.json'),JSON.stringify({blur,click,tab,before,after,end,layouts,keyboard:'Reduced viewport emulation; physical device NOT_RUN'},null,2));
  expect(run.calls.filter(c=>c.method==='POST'&&c.url.endsWith('/turns'))).toHaveLength(0);
});


test('UI E: shared product identity in existing header markup at 1440/390/320', async ({page,context}) => {
  // Static screen states reuse the production HTML/CSS; no registration or separate Cycle.
  await page.route('**/web/dist/**',route=>route.abort());
  await page.goto(base);
  const scenes=['auth-panel','onboarding-panel','auth-complete-panel','prechat-panel','interview-panel','dashboard-panel',
    'report-panel','processing-panel','admin-panel','admin-organizations-panel','admin-assessment-empty-panel','ai-welcome-panel','chat-panel'];
  const results=[];
  const nav=await page.locator('.dashboard-topbar-actions,.interview-topbar-actions').allTextContents();
  for (const width of [1440,390,320]) {
    await page.setViewportSize({width,height:844});
    for (const scene of scenes) {
      await page.evaluate(id=>{
        document.querySelectorAll('.shell > section.panel').forEach(n=>n.classList.add('hidden'));
        const panel=document.getElementById(id);panel.classList.remove('hidden');
        if(id==='auth-complete-panel') panel.classList.add('w02-waiting');
      },scene);
      for (const offline of [false,true]) {
        await context.setOffline(offline);
        const brands=await page.locator('.product-brand').evaluateAll(nodes=>nodes.filter(n=>n.getClientRects().length).map(n=>{
          const s=getComputedStyle(n);return {text:n.textContent,size:s.fontSize,font:s.fontFamily,weight:s.fontWeight,
            before:getComputedStyle(n,'::before').content,after:getComputedStyle(n,'::after').content};}));
        for(const brand of brands) {
          expect(brand.text).toBe('4К Ассистент');expect(brand.size,`${scene} ${width} ${JSON.stringify(brand)}`).toBe(width===1440?'20px':'18px');
          expect(brand.weight).toBe('700');expect(brand.font).toContain('Onest');
          expect(['none','normal']).toContain(brand.before);expect(['none','normal']).toContain(brand.after);
        }
        expect(brands.length).toBeGreaterThan(0);
        if(scene==='report-panel') await expect(page.locator('#report-panel [data-app-header]')).toBeVisible();
        results.push({width,scene,offline,brands});
      }
    }
  }
  expect(await page.locator('.dashboard-topbar-actions,.interview-topbar-actions').allTextContents()).toEqual(nav);
  await context.setOffline(false);
  await fs.writeFile(path.join(evidence,'headers.json'),JSON.stringify({results,navPreserved:true,
    report:'FIX-02 uses the shared POSTW02 product header; product identity is preserved offline and at all widths'},null,2));
});
