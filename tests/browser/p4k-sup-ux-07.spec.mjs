import { test, expect } from '@playwright/test';
import { startAdminProgramPreview } from '../../scripts/adm-program-ui-preview.mjs';

const cycle = 'f3fb5364-6e1d-4448-81e8-ae6ae81600af';
const reference = 'RPT-' + cycle.toUpperCase();
const reportId = 'ea76d884-3209-4fde-b123-f49654d192b5';
const resultId = 'cffafd68-cc24-4fea-9db1-a67fc7b148f1';
const support = '/users/admin/support/reports';
const supportPath = support + '/' + cycle;
const customerPath = '/users/admin/m8-access/reports/' + reportId;
const recoveryPath = '/users/admin/assessment/m8/cycles/' + cycle + '/processing-recovery';
const failed = {
  kind: 'report', reference, cycle_id: cycle, organization_id: 3, state: 'failed',
  preparation_reference: 'P4K-D979620D83CD91D6B3B41F1F', stage_label: 'Сборка отчёта',
  collection_closed_at: '2026-11-21T06:32:00Z', last_confirmed_at: '2026-11-21T06:36:00Z',
  read_at: '2026-11-21T06:39:00Z', results_status: 'saved', results_revision_id: resultId,
  report_status: 'not_created', report_access: 'unavailable', recovery_revision: null,
  handoff_text: 'Cycle: ' + cycle,
};
const limited = { ...failed, state: 'limited', stage_label: 'Отчёт сохранён',
  report_status: 'ready', report_id: reportId, report_openable: true, report_revision: 2,
  report_access: 'allowed', report_results_revision_id: resultId };

let preview;
test.beforeAll(async () => { preview = await startAdminProgramPreview({ port: 18981 }); });
test.afterAll(async () => { await preview?.close(); });

for (const width of [1440, 390, 320]) {
  test('UX-07 report failure and exact PDF retry at ' + width + ' px', async ({ page }, info) => {
    await page.setViewportSize({ width, height: width === 1440 ? 1000 : 844 });
    let saved = failed;
    const exactReads = [], pdfCalls = [];
    await page.route('**' + support + '**', (route) => {
      const url = new URL(route.request().url());
      expect(route.request().method()).toBe('GET');
      if (url.pathname === support) return route.fulfill({ json: { items: [failed] } });
      expect(url.pathname).toBe(supportPath);
      exactReads.push(url.searchParams.get('report_id'));
      return saved ? route.fulfill({ json: saved }) : route.fulfill({ status: 503, json: {} });
    });
    await page.route('**' + customerPath + '/pdf', route => {
      pdfCalls.push(route.request().method());
      return pdfCalls.length === 1 ? route.fulfill({ status: 503, json: {} })
        : route.fulfill({ body: '%PDF-synthetic', contentType: 'application/pdf' });
    });
    await page.route('**' + recoveryPath, route => {
      throw Error('Сверка и PDF не должны вызывать восстановление: ' + route.request().url());
    });
    const root = page.locator('#platform-problems');
    const check = root.getByRole('button', { name: 'Проверить состояние', exact: true });
    const capture = async (name, isSupport = true) => {
      await page.evaluate(() => document.fonts.ready);
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(width);
      if (isSupport) {
        const metrics = await root.evaluate(node => ({
          font: getComputedStyle(node.querySelector('h1')).fontFamily,
          color: getComputedStyle(node.querySelector('h1')).color,
          columns: getComputedStyle(node.querySelector('.support-grid')).gridTemplateColumns.split(' ').length,
        }));
        expect(metrics).toEqual({ font: expect.stringContaining('Onest'), color: 'rgb(34, 44, 48)', columns: width === 1440 ? 2 : 1 });
      }
      await page.screenshot({ path: info.outputPath(name + '-' + width + '.png'), fullPage: true, scale: 'css' });
    };
    await page.goto(preview.base + '/demo/superadmin/confirmed/');
    await page.getByRole('link', { name: 'Проблемы', exact: true }).click();
    await root.getByRole('link', { name: 'Отчёты', exact: true }).click();
    const problem = root.getByRole('link', { name: 'Отчёт не собран' });
    await problem.focus();
    await page.keyboard.press('Enter');
    await expect(root.getByRole('heading', { name: 'Отчёт не собран' })).toBeVisible();
    await expect(root.getByText('Результаты сохранены', { exact: true })).toBeVisible();
    await expect(root.getByRole('button', { name: /восстановление|PDF/ })).toHaveCount(0);
    await check.focus();
    await capture('product-problem');

    saved = limited;
    await page.keyboard.press('Enter');
    await expect(root.getByRole('heading', { name: 'Отчёт готов с ограничениями' })).toBeVisible();
    await expect(check).toBeFocused();
    await expect(page).toHaveURL(new RegExp('report_id=' + reportId));
    saved = null;
    await check.click();
    await expect(root.getByText(/последний подтверждённый факт\./)).toBeVisible();
    await expect(root.getByText(reportId, { exact: true })).toBeVisible();
    await expect(root.getByRole('button', { name: /PDF/ })).toHaveCount(0);
    saved = limited;
    await check.click();
    await expect(root.getByRole('link', { name: 'Открыть отчёт' })).toHaveAttribute('href', new RegExp('report_id=' + reportId));
    const retryPdf = root.getByRole('button', { name: 'Повторить скачивание PDF' });
    await root.getByRole('button', { name: 'Скачать PDF' }).click();
    await expect(retryPdf).toBeVisible();
    await expect(retryPdf).toBeFocused();
    await expect(root.getByText('Не удалось скачать PDF. Попробуйте ещё раз.')).toBeVisible();
    await capture('product-support-pdf');
    const download = page.waitForEvent('download');
    await page.keyboard.press('Enter');
    expect((await download).suggestedFilename()).toBe('4k-report-' + reportId + '.pdf');
    expect(exactReads).toEqual([null, null, reportId, reportId]);
    expect(pdfCalls).toEqual(['GET', 'GET']);

    await page.goto(preview.base + '/demo/admin/confirmed/');
    await page.route('**/users/assessment/m8/cycles/' + cycle + '/status', route => route.fulfill({ json: {
      cycle_id: cycle, collection_status: 'collection_closed', results_status: 'failed', report_status: 'not_created',
      processing: { status: 'failed', message: 'Не удалось завершить техническую обработку. Сохранённые ответы не потеряны.' },
      preparation: { kind: 'report', stage_code: 'report', stage_label: 'Собираем отчёт', status: 'failed',
        reference: failed.preparation_reference, stage_started_at: failed.collection_closed_at, read_at: failed.read_at },
    } }));
    await page.evaluate(async ({ cycle }) => {
      const { openProcessing } = await import('/web/js/screens/processing.js');
      openProcessing({ cycleId: cycle });
    }, { cycle });
    const outcome = page.locator('#processing-outcome-card');
    await expect(outcome.getByRole('heading', { name: 'Не удалось подготовить результат' })).toBeVisible();
    const participantCheck = outcome.getByRole('button', { name: 'Проверить состояние' });
    await participantCheck.focus();
    await expect(participantCheck).toBeFocused();
    await capture('product-failed', false);

    let access = 503;
    let calls = 0;
    let pdfStatus = 503;
    const forbiddenPdf = Promise.withResolvers();
    await page.route('**' + customerPath, route => {
      expect(route.request().method()).toBe('GET');
      return access === 200 ? route.fulfill({ json: {
        id: reportId, cycle_id: cycle, status: 'ready', participant_name: 'Участник 07', program_name: 'Синтетическая оценка',
        collection_closed_at: failed.collection_closed_at, c67: { skills: [], coverage: {}, limitations: [],
          descriptive: { status: 'ready', summary: ['Подтверждённые результаты.'] } },
      } }) : route.fulfill({ status: access, json: {} });
    });
    await page.route('**' + customerPath + '/pdf', async route => {
      expect(route.request().method()).toBe('GET');
      calls += 1;
      if (pdfStatus === 403) await forbiddenPdf.promise;
      return route.fulfill({ status: pdfStatus, json: {} });
    });
    await page.evaluate(async ({ cycle, reportId }) => {
      const { openReport } = await import('/web/js/screens/report.js');
      openReport({ m8CycleId: cycle, m8ReportId: reportId, customerAccess: true });
    }, { cycle, reportId });
    const retryRead = page.locator('#m8-report-state').getByRole('button', { name: 'Повторить', exact: true });
    await expect(retryRead).toBeVisible();
    access = 200;
    await retryRead.focus();
    await page.keyboard.press('Enter');
    const pdf = page.locator('#report-download-button');
    await expect(pdf).toHaveAttribute('data-m8-report-id', reportId);
    await pdf.focus();
    await page.keyboard.press('Enter');
    await expect(pdf).toBeFocused();
    await expect(pdf).toHaveText('Повторить скачивание PDF');
    await expect(page.getByText('Не удалось скачать PDF. Попробуйте ещё раз.')).toBeVisible();
    await expect(page.getByRole('button', { name: /восстановление/ })).toHaveCount(0);
    await capture('product-pdf-error', false);
    pdfStatus = 403;
    try {
      await pdf.press('Enter');
      await expect(pdf).toBeDisabled();
      await expect(pdf).not.toBeFocused();
    } finally {
      forbiddenPdf.resolve();
    }
    await expect(page.locator('#report-download-status')).toHaveText('Доступ к PDF этой редакции недоступен.');
    await expect(page.locator('#report-download-status')).toBeFocused();
    expect(calls).toBe(2);
  });
}

test('UX-07 recovery uses the server revision and rechecks the same Cycle', async ({ page }) => {
  let read = { ...failed, recovery_revision: 17 };
  const commands = [];
  await page.route('**' + supportPath, route => route.fulfill({ json: read }));
  await page.route('**' + recoveryPath, route => {
    expect(route.request().method()).toBe('POST');
    commands.push(route.request().postDataJSON());
    read = { ...failed, state: 'waiting', stage_label: 'Восстановление в очереди' };
    return route.fulfill({ status: 202, json: { recovery_id: 'synthetic', status: 'queued' } });
  });
  await page.goto(preview.base + '/demo/superadmin/confirmed/');
  await page.goto(preview.base + '/?' + new URLSearchParams({ screen: 'admin-platform-problems', kind: 'report', issue: reference }));
  const root = page.locator('#platform-problems');
  const recover = root.getByRole('button', { name: 'Запросить восстановление обработки' });
  await expect(recover).toBeVisible();
  await recover.click();
  await expect(root.getByRole('heading', { name: 'Отчёт готовится' })).toBeVisible();
  await expect(recover).toHaveCount(0);
  expect(commands).toEqual([{ expected_pipeline_revision: 17, idempotency_key: expect.stringMatching(/^[0-9a-f-]{36}$/) }]);
});

test('UX-07 pins the first confirmed Report before retrying an open without an explicit revision', async ({ page }) => {
  let statusReads = 0;
  let reads = 0;
  await page.route('**/users/assessment/m8/cycles/' + cycle + '/status', route => {
    statusReads += 1;
    return route.fulfill({ json: { cycle_id: cycle, report_status: 'ready', results_status: 'ready',
      report_id: statusReads === 1 ? reportId : 'unselected-newer-revision' } });
  });
  await page.route('**/users/assessment/m8/reports/' + reportId, route => {
    reads += 1;
    return reads === 1 ? route.fulfill({ status: 503, json: {} }) : route.fulfill({ json: {
      id: reportId, cycle_id: cycle, owner_user_id: 18, status: 'ready',
      c67: { skills: [], coverage: {}, descriptive: { status: 'ready', summary: [] } },
    } });
  });
  await page.goto(preview.base + '/demo/admin/confirmed/');
  await page.evaluate(async cycleId => {
    const [{ state }, { openReport }] = await Promise.all([
      import('/web/js/state.js'), import('/web/js/screens/report.js'),
    ]);
    state.pendingUser = { id: 18 };
    openReport({ m8CycleId: cycleId });
  }, cycle);
  const retry = page.locator('#m8-report-state').getByRole('button', { name: 'Повторить', exact: true });
  await expect(retry).toBeVisible();
  await expect(page).toHaveURL(new RegExp('report_id=' + reportId));
  await retry.focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#m8-report-state')).toHaveText('Результат готов');
  expect(statusReads).toBe(1);
  expect(reads).toBe(2);
});
