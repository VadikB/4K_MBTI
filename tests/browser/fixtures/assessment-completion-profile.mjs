import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';

const sha256 = (file) => createHash('sha256').update(fs.readFileSync(file)).digest('hex');

async function json(response, label) {
  if (!response.ok()) throw new Error(`${label}: HTTP ${response.status()}`);
  return response.json();
}
async function runtime(page, base, cycleId) {
  return json(await page.request.get(`${base}/users/assessment/cycles/${cycleId}/runtime`), 'runtime');
}

async function waitRuntime(page, base, cycleId, predicate, timeout = 120000) {
  const started = Date.now();
  let last;
  while (Date.now() - started < timeout) {
    last = await runtime(page, base, cycleId);
    if (predicate(last)) return last;
    await page.waitForTimeout(500);
  }
  throw new Error(`completion profile timeout: ${JSON.stringify({
    cycle: cycleId,
    status: last?.status?.collection_status,
    situation: last?.current_situation?.assessment_situation_id,
    clarification: last?.clarification?.status,
    pipeline: last?.pipeline?.status,
  })}`);
}

async function submit(page, text) {
  await page.locator('#interview-textarea').fill(text);
  const response = page.waitForResponse((item) => item.request().method() === 'POST'
    && /^\/users\/assessment\/(m5\/situations\/[^/]+\/turns|m7\/clarifications\/[^/]+\/answers)$/.test(new URL(item.url()).pathname));
  await page.locator('#interview-submit-button').click();
  const accepted = await response;
  if (!accepted.ok()) throw new Error(`answer rejected: HTTP ${accepted.status()}`);
  await page.locator('#interview-error').waitFor({ state: 'hidden' });
}

/**
 * Continue an already presented AS through product UI. The callback only advances
 * the controlled test gateway; real-provider callers omit it and use product workers.
 */
export async function completeStartedAssessment({
  page, base, cycleId, runId, evidenceDir, initialSituationId,
  answerFor = (position) => `Синтетический технический ответ для ситуации ${position}. Уточняю условия, фиксирую решение и проверяю понимание участников.`,
  clarificationFor = (position) => `Синтетическое уточнение ${position}: поясняю основание решения и границы договорённости.`,
  advanceWorkers = async () => {}, maxSituations = 12,
}) {
  const stages = [];
  const before = await runtime(page, base, cycleId);
  if (before.cycle_id !== cycleId || before.current_situation?.assessment_situation_id !== initialSituationId) {
    throw new Error('COMPOSITE_INITIAL_CONTEXT_MISMATCH');
  }
  stages.push({ stage: 'first_case_started', cycle_id: cycleId,
    assessment_situation_id: initialSituationId, status: 'milestone' });

  const seen = new Set();
  for (let position = 1; position <= maxSituations; position += 1) {
    let snapshot = await runtime(page, base, cycleId);
    if (!snapshot.current_situation) break;
    const situationId = snapshot.current_situation.assessment_situation_id;
    if (seen.has(situationId)) throw new Error('COMPOSITE_SITUATION_REPEATED');
    seen.add(situationId);
    const turnCountBefore = (snapshot.trace?.turns || []).filter((turn) => turn.speaker_type === 'assessee').length;
    await submit(page, answerFor(position, snapshot));
    await advanceWorkers();
    snapshot = await waitRuntime(page, base, cycleId, (value) =>
      (value.trace?.turns || []).filter((turn) => turn.speaker_type === 'assessee').length > turnCountBefore);

    const transition = page.waitForResponse((item) => item.request().method() === 'POST'
      && new URL(item.url()).pathname.endsWith('/transitions'));
    await page.locator('#interview-finish-button').click();
    if (!(await transition).ok()) throw new Error('SCENARIO_END_REJECTED');
    await advanceWorkers();
    snapshot = await waitRuntime(page, base, cycleId, (value) =>
      (value.clarification?.status === 'ASK' && !value.clarification?.response_outcome)
      || value.finish_availability?.allowed === true || value.between_situations === true);

    let clarified = false;
    if (snapshot.clarification?.status === 'ASK' && !snapshot.clarification?.response_outcome) {
      await submit(page, clarificationFor(position, snapshot));
      clarified = true;
      await advanceWorkers();
      snapshot = await waitRuntime(page, base, cycleId, (value) => value.finish_availability?.allowed === true);
    }
    if (!snapshot.between_situations) {
      const closed = page.waitForResponse((item) => item.request().method() === 'POST'
        && new URL(item.url()).pathname.endsWith('/finish-situation'));
      await page.locator('#interview-finish-button').click();
      if (!(await closed).ok()) throw new Error('SITUATION_CLOSE_REJECTED');
      await advanceWorkers();
      snapshot = await waitRuntime(page, base, cycleId, (value) => value.between_situations === true
        || ['collection_closed', 'calculation_pending', 'calculated'].includes(value.status?.collection_status));
    }
    stages.push({ stage: 'assessment_situation_closed', position, cycle_id: cycleId,
      assessment_situation_id: situationId, clarified, status: 'completed',
      assessee_turns: (snapshot.trace?.turns || []).filter((turn) => turn.speaker_type === 'assessee').length });

    if (!snapshot.between_situations) break;
    const next = page.getByRole('button', { name: /Приступить к следующей ситуации|Повторить подготовку/ });
    await next.waitFor({ state: 'visible' });
    const nextResponse = page.waitForResponse((item) => item.request().method() === 'POST'
      && new URL(item.url()).pathname.endsWith('/next'));
    await next.click();
    if (!(await nextResponse).ok()) throw new Error('NEXT_REJECTED');
    await advanceWorkers();
    snapshot = await waitRuntime(page, base, cycleId, (value) =>
      value.current_situation?.assessment_situation_id !== situationId
      || ['collection_closed', 'calculation_pending', 'calculated'].includes(value.status?.collection_status));
    if (!snapshot.current_situation) break;
  }

  await advanceWorkers();
  const userId = await page.evaluate(() => JSON.parse(localStorage.getItem('agent4k.pendingUser') || 'null')?.id);
  if (!userId) throw new Error('REPORT_OWNER_MISSING');
  const started = Date.now();
  let journey;
  while (Date.now() - started < 180000) {
    journey = await json(await page.request.get(`${base}/users/${userId}/journey-state`), 'journey');
    if (journey.report_status === 'ready') break;
    if (journey.assessment?.status === 'failed') throw new Error('REPORT_PIPELINE_FAILED');
    await advanceWorkers();
    await page.waitForTimeout(500);
  }
  if (journey?.report_status !== 'ready') throw new Error('REPORT_NOT_READY');
  await page.goto(`${base}/?screen=processing&cycle_id=${encodeURIComponent(cycleId)}`);
  await page.locator('#processing-outcome-title').waitFor({ state: 'visible', timeout: 70000 });
  await page.getByRole('button', { name: 'Посмотреть результат' }).click();
  await page.locator('#report-panel').waitFor({ state: 'visible' });
  const report = await json(await page.request.get(
    `${base}/users/assessment/m8/cycles/${cycleId}/reports/latest`), 'report');
  if (report.cycle_id !== cycleId) throw new Error('REPORT_CYCLE_MISMATCH');
  const screenshot = path.join(evidenceDir, 'available-report.png');
  await page.screenshot({ path: screenshot, fullPage: true });
  stages.push({ stage: 'report_opened', status: 'completed', cycle_id: cycleId,
    report_id: report.id, results_revision_id: report.results_revision_id,
    report_revision_no: report.revision_no, owner_user_id: userId,
    screenshot: path.basename(screenshot), screenshot_sha256: sha256(screenshot) });
  return { contract: 'assessment-execution-contour/1', run_id: runId,
    scope: 'synthetic_technical', cycle_id: cycleId, initial_assessment_situation_id: initialSituationId,
    situation_count: seen.size, report_id: report.id, results_revision_id: report.results_revision_id,
    stages, substitutions: ['scripted_participant'], report_opened: true };
}
