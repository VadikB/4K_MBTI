import { expect, test } from '@playwright/test';
import { spawn, spawnSync } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { once } from 'node:events';
import { closeSync, mkdirSync, openSync } from 'node:fs';
import path from 'node:path';

const checkLabel = 'Проверить состояние';
const statuses = {
  first_failed: 'Не удалось подготовить оценку',
  unknown_failure: 'Не удалось подготовить оценку',
  failed: 'Не удалось завершить подготовку следующей ситуации',
  processing_failed: 'Не удалось обработать результат',
  running: 'Проверяем материалы ситуации',
  stale: 'Последний известный этап: Проверяем материалы ситуации',
  sent: 'Письмо отправлено',
  ready: 'Отчёт готов',
};

function deferred() {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
}

async function rowGeometry(row) {
  return row.evaluate((node) => {
    const rect = (element) => {
      const box = element.getBoundingClientRect();
      return { left: box.left, right: box.right, top: box.top, bottom: box.bottom, center: (box.top + box.bottom) / 2 };
    };
    const type = (selector) => {
      const style = getComputedStyle(node.querySelector(selector));
      return [style.fontSize, style.lineHeight, style.fontWeight];
    };
    const name = '.admin-organization-member-name';
    const badge = '.admin-organization-current-stage';
    const stage = '.admin-organization-member-stage';
    return {
      row: rect(node), identity: rect(node.children[0]), stage: rect(node.children[1]), actions: rect(node.children[2]),
      width: innerWidth, scrollWidth: document.documentElement.scrollWidth, scale: visualViewport.scale, dpr: devicePixelRatio,
      nameType: type(name), badgeType: type(badge), detailType: type(stage + ' span'),
      badgeColor: getComputedStyle(node.querySelector(badge)).backgroundColor,
    };
  });
}

test('ADM-VIS-02 · Состояние, карточка и точная отмена на локальном PostgreSQL', async ({ page, context }, info) => {
  test.setTimeout(120000);
  if (!process.env.STAND_ADMIN_URL) throw new Error('Explicit isolated STAND_ADMIN_URL required');
  const port = 18883;
  const base = `http://127.0.0.1:${port}`;
  const listUrl = base + '/users/admin/organizations';
  const stand = info.outputPath('state.json');
  const python = process.env.BROWSER_PYTHON || path.join(process.cwd(), '.venv/bin/python');
  mkdirSync(path.dirname(stand), { recursive: true });
  const run = (file, action, options = []) => {
    const result = spawnSync(python, [file, action, '--state', stand, ...options], { encoding: 'utf8', timeout: 45000 });
    if (result.status !== 0) throw new Error(`${action}: ${result.error || result.stderr}`);
    return result.stdout.trim().split('\n').at(-1);
  };
  const cli = (action) => run('scripts/test_stand.py', action, ['--port', String(port)]);
  const input = (action) => run('tests/path_admin_browser_inputs.py', action);
  const readback = () => JSON.parse(input('cabinet-state'));
  let server;
  cli('create');
  try {
    cli('bootstrap');
    cli('seed');
    const fixture = JSON.parse(input('visual-states'));
    const id = fixture.organization_id;
    const log = openSync(info.outputPath('server.log'), 'w');
    server = spawn(python, ['scripts/test_stand.py', 'serve', '--state', stand, '--no-workers'], { stdio: ['ignore', log, log] });
    closeSync(log);
    await expect.poll(async () => (await fetch(base + '/health/ready').catch(() => null))?.status, { timeout: 30000 }).toBe(200);
    await context.addCookies([{ name: fixture.cookie_name, value: fixture.session, url: base }]);
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);

    const open = async (tab) => {
      await tab.goto(base);
      await tab.locator('#admin-organization-select').selectOption(String(id));
      await tab.waitForLoadState('networkidle');
    };
    const row = (key, tab = page) => tab.locator(`[data-organization-id="${id}"] [data-member-user-id="${fixture.members[key]}"]`);
    const name = (key, tab = page) => row(key, tab).locator('[data-action="open-member-card"]');
    const action = (key) => row(key).getByRole('button', { name: checkLabel, exact: true });
    const stage = (key) => row(key).locator('.admin-organization-current-stage');
    const status = (tab = page) => tab.locator('#admin-organizations-status');
    const dialog = page.locator('dialog.org-admin-member-card');
    const close = dialog.getByRole('button', { name: 'Закрыть карточку' });
    const feedback = dialog.locator('[data-card-check-feedback]');
    const caseNumber = dialog.locator('[data-card-case] code');
    const requestIsRead = (response) => response.url() === listUrl && response.request().method() === 'GET';
    const project = (data, key) => data.items.find((item) => item.id === id)
      .members.find((member) => member.user_id === fixture.members[key]).assessment_stages[fixture.ref];
    const errors = [];
    const writes = [];
    page.on('pageerror', (error) => errors.push(error.message));
    page.on('request', (request) => {
      if (new URL(request.url()).pathname.startsWith('/users/') && request.method() !== 'GET') writes.push(request.method());
    });
    await open(page);
    const original = readback();
    const geometry = [];

    await test.step('Четыре ветки статуса, приглашение, отчёт и три ширины', async () => {
      const projection = await (await page.request.get(listUrl)).json();
      const first = project(projection, 'first_failed');
      expect(first).toMatchObject({ assignment_id: fixture.assignments.first_failed, code: 'preparation_failed',
        can_cancel: true, progress: { completed: 0, planned: 8 }, preparation: { kind: 'assessment', stage_code: 'checking' } });
      expect(project(projection, 'failed')).toMatchObject({ assignment_id: fixture.assignments.failed, code: 'paused',
        can_cancel: false, progress: { completed: 2, planned: 8 }, preparation: { kind: 'next', status: 'failed' } });
      expect(fixture.catalog_case_count).not.toBe(8);
      expect(project(projection, 'processing_failed')).toMatchObject({ code: 'failed', action: 'open_processing',
        preparation: { kind: 'report', status: 'failed' } });
      expect(project(projection, 'stale').preparation.freshness).toBe('unconfirmed');
      for (const width of [1440, 390, 320]) {
        await page.setViewportSize({ width, height: 1000 });
        await page.evaluate(() => document.fonts.ready);
        for (const [key, label] of Object.entries(statuses)) {
          await expect(stage(key)).toHaveText(label);
          const { row: bounds, identity, stage: state, actions, ...facts } = await rowGeometry(row(key));
          expect(facts).toMatchObject({ width, scale: 1, dpr: 1, scrollWidth: width,
            nameType: ['14px', '20px', '600'], badgeType: ['13px', '18px', '400'], detailType: ['13px', '19px', '400'] });
          expect(identity.right).toBeLessThanOrEqual(actions.left);
          expect(Math.abs(identity.center - actions.center)).toBeLessThan(1);
          if (width === 1440) {
            expect(identity.right).toBeLessThan(state.left);
            expect(state.right).toBeLessThan(actions.left);
            expect(Math.abs(identity.center - state.center)).toBeLessThan(1);
          } else {
            expect(state.top).toBeGreaterThan(identity.bottom);
            expect(state.top).toBeGreaterThan(actions.bottom);
            expect(state.left).toBe(identity.left);
            expect(state.right).toBe(actions.right);
          }
          if (['first_failed', 'failed', 'processing_failed'].includes(key)) {
            expect(facts.badgeColor).toBe('rgb(255, 229, 224)');
          }
          expect(actions.right).toBeLessThanOrEqual(bounds.right);
          geometry.push({ key, ...facts, bounds, identity, state, actions });
        }
        await expect(row('first_failed').locator('.admin-organization-member-actions button')).toHaveText([checkLabel]);
        await expect(row('first_failed')).toContainText('Требуется проверка материалов первой ситуации.');
        await expect(row('first_failed')).not.toContainText(/AS плана|Ответственный|Номер случая/);
        await expect(row('unknown_failure')).not.toContainText('первой ситуации');
        await expect(row('failed')).toContainText('Оценка приостановлена. Завершено 2 из 8 ситуаций.');
        await expect(row('stale')).toContainText('Сейчас не можем подтвердить, что подготовка продолжается');
        await expect(row('ready').getByRole('button', { name: 'Открыть отчёт' })).toHaveAttribute('data-report-id', fixture.reports.ready.report_id);
        await name('failed').focus();
        await page.keyboard.press('Tab');
        await expect(action('failed')).toBeFocused();
        const read = page.waitForResponse(requestIsRead);
        await page.keyboard.press('Enter');
        expect((await read).status()).toBe(200);
        await expect(feedback).toHaveText('Состояние обновлено.');
        await expect(dialog.locator('[data-card-last-stage]')).toContainText('Проверяем материалы ситуации');
        await expect(caseNumber).toHaveText(fixture.cases.failed);
        await expect(dialog.locator('[data-card-cancel-assignment]')).toBeHidden();
        await expect(close).toBeFocused();
        await page.keyboard.press('Tab');
        const copy = dialog.getByRole('button', { name: 'Скопировать номер' });
        await expect(copy).toBeFocused();
        await page.keyboard.press('Enter');
        await expect(feedback).toHaveText('Номер скопирован.');
        expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(fixture.cases.failed);
        await page.keyboard.press('Escape');
        await expect(dialog).toHaveCount(0);
        await expect(action('failed')).toBeFocused();
      }
      await page.setViewportSize({ width: 1440, height: 1000 });
      await expect(action('processing_failed')).toHaveCount(0);
      await row('processing_failed').getByRole('button', { name: 'Подробнее об обработке' }).click();
      const processing = page.getByRole('dialog', { name: 'Ошибка обработки результата' });
      await expect(processing).toContainText('Результат пока недоступен.');
      await expect(processing).not.toContainText(/Готовится отчёт|Сведения о подготовке/);
      await page.keyboard.press('Escape');
      await expect(processing).toHaveCount(0);
    });

    await test.step('Потеря ответа GET и повтор по тому же назначению', async () => {
      await page.route(listUrl, async (route) => {
        const confirmed = await route.fetch();
        expect(confirmed.status()).toBe(200);
        await route.abort('failed');
      }, { times: 1 });
      await action('first_failed').click();
      await expect(feedback).toContainText('Не удалось обновить состояние.');
      await expect(caseNumber).toHaveText(fixture.cases.first_failed);
      await expect(page.locator('[data-organizations-stale]')).toBeVisible();
      const successful = page.waitForResponse(requestIsRead);
      await dialog.getByRole('button', { name: checkLabel }).click();
      const body = await (await successful).json();
      expect(project(body, 'first_failed')).toMatchObject({ assignment_id: fixture.assignments.first_failed,
        preparation: { reference: fixture.cases.first_failed } });
      await expect(feedback).toHaveText('Состояние обновлено.');
      await expect(page.locator('[data-organizations-stale]')).toHaveCount(0);
      const prior = fixture.invitations.first_failed;
      const priorInvitation = dialog.locator('.admin-invitation-details');
      await priorInvitation.getByText('Сведения о приглашении', { exact: true }).click();
      const receiptRead = page.waitForResponse((response) =>
        new URL(response.url()).pathname.endsWith('/personal-invitations/operations/' + prior.operation));
      await priorInvitation.getByRole('button', { name: 'Обновить сведения' }).click();
      const receipt = await receiptRead;
      expect(receipt.status()).toBe(200);
      expect(receipt.request().method()).toBe('GET');
      expect(new URL(receipt.url()).searchParams.get('assignment_ref')).toBe(prior.ref);
      expect((await receipt.json()).items).toEqual([expect.objectContaining({ invitation_id: prior.id, email: prior.email })]);
      await dialog.locator('[data-card-cancel-assignment]').click();
      await expect(page.getByRole('dialog', { name: 'Отменить назначение?' })).toContainText('Сбой до старта');
      await page.keyboard.press('Escape');
      await expect(dialog.locator('[data-card-cancel-assignment]')).toBeFocused();
      await page.keyboard.press('Escape');
      await expect(action('first_failed')).toBeFocused();
    });

    await test.step('Уход в другую организацию во время чтения', async () => {
      const captured = deferred();
      const release = deferred();
      await page.route(listUrl, async (route) => {
        const response = await route.fetch();
        captured.resolve();
        await release.promise;
        await route.fulfill({ response });
      }, { times: 1 });
      try {
        await action('stale').click();
        await captured.promise;
        await page.keyboard.press('Escape');
        const picker = page.locator('#admin-organization-select');
        await picker.selectOption(String(fixture.peer_org));
        await expect(page.locator(`[data-organization-id="${fixture.peer_org}"]`)).toBeVisible();
        const previousStatus = await status().textContent();
        const completed = page.waitForResponse(requestIsRead);
        release.resolve();
        await (await completed).finished();
        await expect(picker).toHaveValue(String(fixture.peer_org));
        await expect(dialog).toHaveCount(0);
        await expect(status()).toHaveText(previousStatus);
        await picker.selectOption(String(id));
        await expect(stage('stale')).toHaveText(statuses.stale);
      } finally {
        release.resolve();
      }
      expect(writes).toEqual([]);
      expect(readback()).toEqual(original);
    });

    const subjectDialog = (tab = page) => tab.getByRole('dialog', { name: 'Отменить назначение?' });
    const confirm = (tab = page) => subjectDialog(tab).getByRole('button', { name: 'Отменить назначение', exact: true });
    const cancelUrl = (key) => `${listUrl}/${id}/assessment-assignments/${fixture.assignments[key]}/cancel`;
    await test.step('Потеря ответа POST отмены и новое поколение во время старого чтения', async () => {
      const second = await context.newPage();
      const release = deferred();
      try {
        await open(second);
        await name('unknown_failure').click();
        await expect(dialog.locator('[data-card-last-stage]')).toBeHidden();
        const captured = deferred();
        await page.route(listUrl, async (route) => {
          captured.resolve();
          await release.promise;
          await route.continue();
        }, { times: 1 });
        await dialog.getByRole('button', { name: checkLabel }).click();
        await captured.promise;
        const url = cancelUrl('unknown_failure');
        await second.route(url, async (route) => {
          const response = await route.fetch();
          expect(response.status()).toBe(200);
          expect(await response.json()).toMatchObject({ assignment_id: fixture.assignments.unknown_failure,
            recipient_user_id: fixture.members.unknown_failure, organization_id: id, status: 'revoked' });
          await route.abort('failed');
        }, { times: 1 });
        await name('unknown_failure', second).click();
        await second.locator('[data-card-cancel-assignment]').click();
        await confirm(second).click();
        await expect(status(second)).toHaveText('Отмена подтверждена чтением после потери ответа команды.');
        const reassigned = await second.request.post(`${listUrl}/${id}/assessment-assignments`, { data: {
          user_ids: [fixture.members.unknown_failure], assignment_ref: fixture.ref,
          role_profile_version_id: fixture.role, operation_id: randomUUID(),
        } });
        expect(reassigned.status()).toBe(200);
        const newId = (await reassigned.json()).items[0].assignment_id;
        expect(newId).not.toBe(fixture.assignments.unknown_failure);
        const updated = page.waitForResponse(requestIsRead);
        release.resolve();
        const current = project(await (await updated).json(), 'unknown_failure');
        expect(current).toMatchObject({ assignment_id: newId, code: 'acquaintance_complete' });
        await expect(feedback).toHaveText('Назначение изменилось. Откройте карточку заново.');
        await expect(dialog.locator('[data-card-incident]')).toBeHidden();
        await expect(dialog.locator('[data-card-cancel-assignment]')).toBeHidden();
        await page.keyboard.press('Escape');
        await expect(stage('unknown_failure')).toHaveText(current.label);
      } finally {
        release.resolve();
        await second.close();
      }
      expect(writes).toEqual([]);
    });

    await test.step('Сервер отклоняет отмену после старта с кодом 409', async () => {
      await name('first_failed').click();
      await dialog.locator('[data-card-cancel-assignment]').click();
      expect(writes).toEqual([]);
      input('cabinet-race-start');
      const conflict = page.waitForResponse((response) => response.url() === cancelUrl('first_failed'));
      await confirm().click();
      const response = await conflict;
      expect(response.status()).toBe(409);
      expect(await response.json()).toEqual({ detail: 'ASSIGNMENT_ALREADY_STARTED' });
      await expect(stage('first_failed')).toHaveText('Оценка выполняется');
      await expect(status()).toContainText('больше не может быть отменено');
      await name('first_failed').click();
      await expect(dialog.locator('[data-card-cancel-assignment]')).toBeHidden();
      await page.keyboard.press('Escape');
      expect(writes).toEqual(['POST']);
      expect(readback().cancellations).toEqual([{ assignment_id: fixture.assignments.unknown_failure, count: 1 }]);
    });

    expect(errors).toEqual([]);
    await info.attach('viewports', { body: JSON.stringify({ catalogCases: fixture.catalog_case_count, geometry }),
      contentType: 'application/json' });
  } finally {
    if (server?.exitCode === null) {
      const ended = once(server, 'exit');
      server.kill('SIGTERM');
      await ended;
    }
    cli('destroy');
  }
});
