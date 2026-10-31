import { test, expect } from '@playwright/test';
import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { randomUUID } from 'node:crypto';

test('ADM28 real isolated backend: draft, recipients, publication, self-assignment and own journey', async ({ page }) => {
  test.setTimeout(240000);
  if (!process.env.STAND_ADMIN_URL) throw new Error('Explicit isolated STAND_ADMIN_URL required');
  const root = process.cwd();
  const python = process.env.BROWSER_PYTHON || path.join(root, '.venv/bin/python');
  const dir = path.join(root, '.test-stand/adm28', randomUUID());
  fs.mkdirSync(dir, { recursive: true });
  const statePath = path.join(dir, 'state.json');
  const cli = (action) => {
    const result = spawnSync(python, ['scripts/test_stand.py', action, '--state', statePath, '--port', '18844', '--gateway', '1'], { encoding: 'utf8' });
    if (result.status !== 0) throw new Error(action + ': ' + result.stderr);
  };
  let server;
  cli('create');
  try {
    cli('bootstrap');
    cli('seed');
    const fixture = spawnSync(python, ['scripts/adm28_browser_fixture.py', '--state', statePath], { encoding: 'utf8' });
    if (fixture.status !== 0) throw new Error(fixture.stderr);
    const state = JSON.parse(fs.readFileSync(statePath, 'utf8'));
    const fd = fs.openSync(path.join(dir, 'server.log'), 'a');
    server = spawn(python, ['scripts/test_stand.py', 'serve', '--state', statePath], { stdio: ['ignore', fd, fd] });
    fs.closeSync(fd);
    const base = 'http://127.0.0.1:18844';
    await expect.poll(async () => { try { return (await fetch(base + '/health/ready')).status; } catch { return 0; } }, { timeout: 30000 }).toBe(200);
    let starts = 0;
    page.on('request', (request) => {
      if (request.method() === 'POST' && /\/(?:assessment|cycles)\/start/.test(request.url())) starts += 1;
    });
    await page.goto(base);
    await page.locator('#email-input').fill('admin@example.test');
    await page.locator('#request-magic-link-button').click();
    await page.locator('#magic-token-input').fill(state.password);
    await page.locator('#verify-magic-link-button').click();
    await expect(page.locator('#admin-organizations-panel')).toBeVisible();
    await page.getByRole('button', { name: 'К сводке', exact: true }).click();
    await expect(page.locator('#admin-panel')).toBeVisible();
    await expect(page.locator('#admin-insights-grid')).toContainText('Пока нет данных для выводов');
    await expect(page.locator('#admin-insights-grid')).not.toContainText('Наиболее слабый контур');
    await expect(page.locator('#admin-insights-grid')).not.toContainText('Лучшая группа');
    await page.locator('#admin-open-organizations-button').click();
    await expect(page.locator('#admin-organizations-panel')).toBeVisible();
    const card = page.locator('.admin-organization-card');
    const organizationId = await card.getAttribute('data-organization-id');
    await expect(card.locator('.admin-assignment-readiness')).toContainText('Оценка не выбрана');
    await expect(card.getByRole('button', { name: 'Назначить оценку', exact: true })).toBeDisabled();
    await card.getByRole('button', { name: 'Данные организации', exact: true }).click();
    const profile = card.locator('form[data-action="update-profile"]');
    await profile.getByRole('button', { name: 'Сохранить карточку' }).click();
    await expect(profile.locator('[data-operation-status]')).toContainText('Карточка организации сохранена');
    const form = card.locator('form[data-action="preview-early-data"]');
    const values = { assignment_ref: 'ADM28 isolated', source_author: 'Синтетический заказчик',
      organization_name: 'Синтетическая организация ADM28', organization_type: 'Компания', industry: 'ИТ',
      activity_description: 'Синтетическая проверка', purpose: 'Синтетическая цель', results_usage: 'Для развития',
      result_recipients: 'Участник', organizer: 'Синтетический HR', responsible_contact: 'admin@example.test',
      case_reality_level: 'Реальные', organization_name_usage_rules: 'Разрешено' };
    for (const [name, value] of Object.entries(values)) await form.locator(`[name="${name}"]`).fill(value);
    await form.getByRole('button', { name: 'Сохранить черновик и предпросмотр' }).click();
    const preview = card.locator('.admin-questionnaire-preview');
    await expect(preview).toContainText('Готово к подтверждению');
    const revisionId = await preview.getAttribute('data-questionnaire-revision-id');
    const toggle = preview.locator('[name="questionnaire_recipient"][value="organization_admin"]');
    await toggle.check();
    await expect(preview.getByRole('button', { name: 'Подтвердить сведения' })).toBeDisabled();
    await preview.locator('[name="questionnaire_recipient_user"]').check();
    await card.getByRole('button', { name: 'Организация и участники', exact: true }).click();
    await card.getByRole('button', { name: 'Данные организации', exact: true }).click();
    await expect(toggle).toBeChecked();
    await expect(preview.locator('[name="questionnaire_recipient_user"]')).toBeEnabled();
    await preview.getByRole('button', { name: 'Подтвердить сведения' }).click();
    await expect(card.locator('.admin-questionnaire-confirmation')).toContainText('Сведения подтверждены');
    const savedResponse = await page.request.get(`${base}/users/admin/organizations/${organizationId}/questionnaire/${revisionId}`);
    expect(savedResponse.status()).toBe(200);
    const saved = await savedResponse.json();
    expect(saved.status).toBe('confirmed');
    expect(saved.recipient_user_ids).toHaveLength(1);
    expect(saved.recipient_mapping.sort()).toEqual(['organization_admin', 'participant']);
    // Same content is idempotent; changed recipients are an explicit conflict.
    expect((await page.request.post(`${base}/users/admin/organizations/${organizationId}/questionnaire/${revisionId}/confirm`, {
      data: { recipients: saved.recipient_mapping, recipient_user_ids: saved.recipient_user_ids },
    })).status()).toBe(200);
    expect((await page.request.post(`${base}/users/admin/organizations/${organizationId}/questionnaire/${revisionId}/confirm`, {
      data: { recipients: ['participant'], recipient_user_ids: [] },
    })).status()).toBe(409);
    await page.reload();
    await expect(form.locator('[name="source_author"]')).toHaveValue(values.source_author);
    await expect(form.locator('[name="purpose"]')).toHaveValue(values.purpose);
    await card.getByRole('button', { name: 'Организация и участники', exact: true }).click();
    await card.locator('input[name="invitation_email"]').evaluateAll((fields) => fields.forEach((field) => {
      field.checked = true;
      field.dispatchEvent(new Event('change', { bubbles: true }));
    }));
    await card.getByRole('button', { name: 'Назначить оценку', exact: true }).click();
    await expect(card.locator('[data-operation-status]')).toContainText('Назначена: 2');
    await expect(card.locator('.admin-organization-member')).toHaveCount(2);
    await expect(card.locator('.admin-organization-member').first()).toContainText('Оценка: назначена');
    const revisions = await (await page.request.get(`${base}/users/admin/organizations/${organizationId}/questionnaire`)).json();
    expect(revisions.items[0].readiness.roles.total).toBe(2);
    expect(revisions.items[0].readiness.roles.status).toBe('incomplete');
    expect(revisions.items[0].readiness.preparation.status).toBe('idle');
    const add = card.locator('form[data-action="add-member"]');
    await add.locator('[name="email"]').fill('added@example.test');
    await add.locator('[name="full_name"]').fill('Синтетический новый участник');
    await add.locator('[name="role_description"]').fill('Синтетический специалист');
    await add.getByRole('button', { name: 'Добавить', exact: true }).click();
    await expect(add.locator('[data-operation-status]')).toContainText('Участник привязан');
    const imported = card.locator('form[data-action="import-members"]');
    await imported.locator('[name="csv"]').setInputFiles({ name: 'synthetic.csv', mimeType: 'text/csv',
      buffer: Buffer.from('email,full_name,role_description,job_instructions\nimported@example.test,Синтетический импорт,Специалист,Проверять примеры\n') });
    await imported.getByRole('button', { name: 'Импорт', exact: true }).click();
    await expect(imported.locator('[data-operation-status]')).toContainText('Импортировано: 1');
    await card.locator('input[name="invitation_email"]').evaluateAll((fields) => fields.forEach((field) => { field.checked = false; }));
    await card.locator('input[name="invitation_email"][value="added@example.test"]').check();
    await card.getByRole('button', { name: 'Отправить приглашения', exact: true }).click();
    await expect(card.locator('form[data-action="send-member-invitations"] [data-operation-status]')).toContainText('Сервис приглашений не настроен');
    for (const width of [1440, 1280, 390, 320]) {
      await page.setViewportSize({ width, height: 936 });
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
      const bounds = await card.evaluate((element) => {
        const outer = element.getBoundingClientRect();
        return [...element.querySelectorAll('input, textarea, button')]
          .filter((control) => control.getClientRects().length && !control.closest('nav'))
          .filter((control) => { const rect = control.getBoundingClientRect(); return rect.left < outer.left - 1 || rect.right > outer.right + 1; })
          .map((control) => control.getAttribute('name') || control.textContent);
      });
      expect(bounds, `controls must fit the organization workspace at ${width}px`).toEqual([]);
      await page.screenshot({ path: path.join(dir, `management-${width}.png`), fullPage: true });
    }
    await page.setViewportSize({ width: 1440, height: 936 });
    await page.getByRole('button', { name: 'Моя оценка', exact: true }).click();
    await expect(page.locator('#onboarding-panel')).toBeVisible();
    await expect(page.locator('#admin-assessment-empty-panel')).toBeHidden();
    await expect(page.locator('#auth-panel')).toBeHidden();
    await page.reload();
    await expect(page.locator('#onboarding-panel')).toBeVisible();
    expect(starts).toBe(0);
    await page.getByRole('button', { name: 'Управление', exact: true }).click();
    await expect(page.locator('#admin-organizations-panel')).toBeVisible();
    const assignments = await (await page.request.get(`${base}/users/admin/organizations`)).json();
    expect(assignments.items[0].members.filter((member) => ['admin@example.test', 'colleague@example.test'].includes(member.email))
      .every((member) => member.assessment_assignments.includes('ADM28 isolated'))).toBe(true);
  } finally {
    if (server && server.exitCode === null) {
      const exited = new Promise((resolve) => server.once('exit', resolve));
      server.kill('SIGTERM');
      await Promise.race([exited, new Promise((resolve) => setTimeout(resolve, 5000))]);
      if (server.exitCode === null) { server.kill('SIGKILL'); await exited; }
    }
    cli('destroy');
  }
});
