import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { persistReceipt } from './receipt-file.mjs';

const sha256 = (file) => createHash('sha256').update(fs.readFileSync(file)).digest('hex');

async function json(response, label) {
  if (!response.ok()) throw new Error(`${label}: HTTP ${response.status()}`);
  return response.json();
}
async function runtime(page, base, cycleId) {
  const value = await json(await page.request.get(`${base}/users/assessment/cycles/${cycleId}/runtime`), 'runtime');
  if (value.cycle_id !== cycleId) throw new Error('COMPOSITE_CYCLE_CHANGED');
  return value;
}

const closedStatuses = ['collection_closed', 'calculation_pending', 'calculated'];
const collectionClosed = (value) => closedStatuses.includes(value?.status?.collection_status);
const presented = (value) => value?.current_situation?.status === 'active'
  && Boolean(value.current_situation.participant_payload);

export async function readExecutionExport(page, base, cycleId, runId, evidenceDir, fault) {
  const value = await json(await page.request.get(`${base}/__pytest__/execution-export/${cycleId}`), 'execution export');
  if (value.run_id !== runId || value.cycle_id !== cycleId || !Array.isArray(value.situations)) {
    throw new Error('EXECUTION_EXPORT_CONTEXT_MISMATCH');
  }
  const file = path.join(evidenceDir, 'terminal-execution-export.json');
  if (fault === 'write') throw new Error('INJECTED_EXECUTION_EXPORT_WRITE_FAILURE');
  const digest = persistReceipt(file, value);
  if (fault === 'readback') fs.appendFileSync(file, 'corrupted readback');
  if (sha256(file) !== digest || JSON.parse(fs.readFileSync(file, 'utf8')).run_id !== runId) {
    throw new Error('EXECUTION_EXPORT_READBACK_MISMATCH');
  }
  return { value, file: path.basename(file), sha256: digest };
}

export function terminalExecutionKnown(value) {
  return closedStatuses.includes(value?.collection_status)
    && Boolean(value.close_reason) && Boolean(value.collection_closed_at)
    && Array.isArray(value.situations)
    && value.situations.some((item) => ['closed', 'terminated'].includes(item.status))
    && !value.situations.some((item) => ['active', 'paused', 'scenario_ended'].includes(item.status))
    && ['ready', 'failed'].includes(value.pipeline?.status);
}

export function destroyOwnedStandIfAdmitted({ executionStarted, terminalExecutionExportSaved,
  preparationReceiptRequired, terminalPreparationReceiptSaved, statePath, runId, save, cli }) {
  if (executionStarted && !terminalExecutionExportSaved) {
    throw new Error('Cleanup deferred: terminal execution export or readback unavailable');
  }
  if (preparationReceiptRequired && !terminalPreparationReceiptSaved) {
    save('cleanup-deferred', { reason: 'TERMINAL_PREPARATION_RECEIPT_NOT_PERSISTED',
      state_path: statePath, database_preserved: true });
    throw new Error('Cleanup deferred: preserve owned DB until diagnostic receipt is saved');
  }
  try { cli('destroy'); }
  catch (cleanupError) {
    save('cleanup-error', { run_id: runId, reason: 'OWNED_DESTROY_FAILED',
      detail: cleanupError.message });
    throw cleanupError;
  }
}

async function waitRuntime(page, base, cycleId, predicate, timeout = 120000) {
  const started = Date.now();
  let last;
  while (Date.now() - started < timeout) {
    last = await runtime(page, base, cycleId);
    if (last.pipeline?.status === 'failed') {
      throw new Error('COMPOSITE_PIPELINE_FAILED: ' + (last.pipeline.error_code || 'UNKNOWN'));
    }
    if (predicate(last)) return last;
    await page.waitForTimeout(500);
  }
  throw new Error(`COMPOSITE_TECHNICAL_TIMEOUT: ${JSON.stringify({
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
    && /^\/users\/assessment\/(m5\/situations\/[^/]+\/turns|m7\/clarifications\/[^/]+\/answers)$/.test(new URL(item.url()).pathname),
    { timeout: 30000 });
  await page.locator('#interview-submit-button').click({ timeout: 15000 });
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
  advanceWorkers = async () => {}, maxSituations = 12, reloadAtBoundary = false,
  stopAfterFirstNext = false, onNextAccepted = async () => null,
}) {
  // The product asks for explicit Finish confirmation. Runtime specs may have
  // already registered this handler during login; two handlers race to accept
  // the same dialog and fail the browser shard.
  if (!page.acceptanceDialogHandler) {
    page.on('dialog', (dialog) => dialog.accept());
    page.acceptanceDialogHandler = true;
  }
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
    if (collectionClosed(snapshot)) break;
    if (!snapshot.current_situation) throw new Error('COMPOSITE_CURRENT_AS_UNKNOWN');
    const situationId = snapshot.current_situation.assessment_situation_id;
    if (seen.has(situationId)) throw new Error('COMPOSITE_SITUATION_REPEATED');
    seen.add(situationId);
    const initialTurnCount = (snapshot.trace?.turns || []).filter((turn) => turn.speaker_type === 'assessee').length;
    if (snapshot.current_situation.status === 'active') {
      if (!presented(snapshot)) throw new Error('COMPOSITE_AS_NOT_PRESENTED');
      await submit(page, answerFor(position, snapshot));
      await advanceWorkers();
      snapshot = await waitRuntime(page, base, cycleId, (value) => collectionClosed(value)
        || value.current_situation?.status === 'scenario_ended'
        || (value.trace?.turns || []).filter((turn) => turn.speaker_type === 'assessee').length > initialTurnCount);
    }
    if (!collectionClosed(snapshot) && snapshot.current_situation?.status === 'active') {
      const transition = page.waitForResponse((item) => item.request().method() === 'POST'
        && new URL(item.url()).pathname.endsWith('/transitions'), { timeout: 30000 });
      await page.locator('#interview-finish-button').click({ timeout: 15000 });
      if (!(await transition).ok()) throw new Error('SCENARIO_END_REJECTED');
      await advanceWorkers();
    }
    snapshot = await waitRuntime(page, base, cycleId, (value) => collectionClosed(value)
      || value.between_situations || value.current_situation?.status === 'scenario_ended');
    let clarified = false;
    while (!collectionClosed(snapshot) && !snapshot.between_situations) {
      if (snapshot.current_situation?.assessment_situation_id !== situationId) {
        throw new Error('COMPOSITE_AS_CHANGED_DURING_CLARIFICATION');
      }
      const ask = snapshot.clarification;
      if (ask?.status === 'ASK' && !ask.response_outcome) {
        if (!ask.id) throw new Error('COMPOSITE_ASK_NOT_DELIVERED');
        if (!ask.question_turn_id) {
          // ASK and its delivery commit separately. Keep the existing bounded
          // readback; never submit an answer before delivery is authoritative.
          snapshot = await waitRuntime(page, base, cycleId, (value) => collectionClosed(value)
            || value.between_situations || value.finish_availability?.allowed === true
            || value.clarification?.status !== 'ASK' || value.clarification?.response_outcome
            || Boolean(value.clarification?.question_turn_id));
          continue;
        }
        await submit(page, clarificationFor(position, snapshot));
        clarified = true;
        await advanceWorkers();
        snapshot = await waitRuntime(page, base, cycleId, (value) => collectionClosed(value)
          || value.between_situations || value.finish_availability?.allowed === true
          || (value.clarification?.id !== ask.id && value.clarification?.status === 'ASK'));
        continue;
      }
      if (snapshot.finish_availability?.allowed === true) break;
      await advanceWorkers();
      snapshot = await waitRuntime(page, base, cycleId, (value) => collectionClosed(value)
        || value.between_situations || value.finish_availability?.allowed === true
        || (value.clarification?.status === 'ASK' && !value.clarification?.response_outcome));
    }
    if (!collectionClosed(snapshot) && !snapshot.between_situations) {
      snapshot = await runtime(page, base, cycleId);
      if (!collectionClosed(snapshot)) {
        if (snapshot.current_situation?.assessment_situation_id !== situationId
            || snapshot.finish_availability?.allowed !== true) throw new Error('COMPOSITE_FINISH_NOT_ADMITTED');
        const closed = page.waitForResponse((item) => item.request().method() === 'POST'
          && new URL(item.url()).pathname.endsWith('/finish-situation'), { timeout: 30000 });
        let clickError;
        try { await page.locator('#interview-finish-button').click({ timeout: 15000 }); }
        catch (error) { clickError = error; }
        let closeResponse;
        try { closeResponse = await closed; }
        catch (error) { throw clickError || error; }
        if (!closeResponse.ok()) throw new Error('SITUATION_CLOSE_REJECTED');
        if (clickError) {
          const committed = await runtime(page, base, cycleId);
          if (!committed.between_situations && !collectionClosed(committed)) throw clickError;
        }
        await advanceWorkers();
        snapshot = await waitRuntime(page, base, cycleId, (value) => value.between_situations === true
          || collectionClosed(value));
      }
    }
    const closedExport = await json(await page.request.get(`${base}/__pytest__/execution-export/${cycleId}`), 'AS close readback');
    const closedAs = closedExport.situations?.find((item) => item.assessment_situation_id === situationId);
    if (!closedAs || !['closed', 'terminated'].includes(closedAs.status)
        || !closedAs.session_id || !closedAs.final_handoff_id || !closedAs.finalization_status) {
      throw new Error('COMPOSITE_AS_CLOSE_NOT_PROVEN');
    }
    stages.push({ stage: 'assessment_situation_closed', position, cycle_id: cycleId,
      session_id: closedAs.session_id, assessment_situation_id: situationId, clarified, status: 'completed',
      close_status: closedAs.status, final_handoff_id: closedAs.final_handoff_id,
      finalization_status: closedAs.finalization_status, assessee_turns_before: initialTurnCount,
      assessee_turns: Number(closedAs.assessee_turns),
      interim_handoffs: Number(closedAs.interim_handoffs), c54_receipts: Number(closedAs.c54_receipts) });

    if (collectionClosed(snapshot)) break;
    if (!snapshot.between_situations) throw new Error('COMPOSITE_NEXT_BOUNDARY_UNKNOWN');
    if (reloadAtBoundary) {
      await page.goto(`${base}/?screen=interview&cycle_id=${encodeURIComponent(cycleId)}`);
    }
    const next = page.getByRole('button', { name: 'Приступить к следующей ситуации' });
    await next.waitFor({ state: 'visible', timeout: 15000 });
    const nextResponse = page.waitForResponse((item) => item.request().method() === 'POST'
      && new URL(item.url()).pathname.endsWith('/next'), { timeout: 30000 });
    await next.click({ timeout: 15000 });
    const nextReceipt = await nextResponse;
    if (!nextReceipt.ok()) throw new Error('NEXT_REJECTED');
    const nextOperation = await nextReceipt.json();
    const hooked = await onNextAccepted({ page, base, cycleId, position, situationId,
      operation: nextOperation });
    if (hooked?.ownershipChanged && stopAfterFirstNext) {
      stages.push({ stage: 'explicit_next_presented', status: 'completed', cycle_id: cycleId,
        previous_assessment_situation_id: situationId,
        next_assessment_situation_id: hooked.nextSituationId,
        operation_id: nextOperation.operation_id,
        stale_owner_result_ignored: true });
      return { contract: 'assessment-first-next/1', run_id: runId,
        scope: 'synthetic_technical', cycle_id: cycleId,
        initial_assessment_situation_id: initialSituationId,
        next_assessment_situation_id: hooked.nextSituationId, stages };
    }
    await advanceWorkers();
    snapshot = await waitRuntime(page, base, cycleId, (value) => collectionClosed(value)
      || (value.current_situation?.assessment_situation_id !== situationId && presented(value)));
    if (collectionClosed(snapshot)) break;
    if (stopAfterFirstNext) {
      const nextSituationId = snapshot.current_situation?.assessment_situation_id;
      if (!nextSituationId || nextSituationId === situationId) throw new Error('COMPOSITE_NEXT_AS_NOT_PRESENTED');
      stages.push({ stage: 'explicit_next_presented', status: 'completed', cycle_id: cycleId,
        previous_assessment_situation_id: situationId,
        next_assessment_situation_id: nextSituationId });
      return { contract: 'assessment-first-next/1', run_id: runId,
        scope: 'synthetic_technical', cycle_id: cycleId,
        initial_assessment_situation_id: initialSituationId,
        next_assessment_situation_id: nextSituationId, stages };
    }
  }

  const closedRuntime = await runtime(page, base, cycleId);
  if (!collectionClosed(closedRuntime)) throw new Error('COMPOSITE_COLLECTION_NOT_CLOSED');
  const terminal = await readExecutionExport(page, base, cycleId, runId, evidenceDir);
  const exported = terminal.value;
  if (!closedStatuses.includes(exported.collection_status) || !exported.close_reason
      || !exported.collection_closed_at || !exported.c46?.id) {
    throw new Error('COMPOSITE_COLLECTION_CLOSE_NOT_PROVEN');
  }
  stages.push({ stage: 'collection_closed', status: 'completed', cycle_id: cycleId,
    close_reason: exported.close_reason, closed_at: exported.collection_closed_at,
    c46_revision_id: exported.c46.id });

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
  if (report.cycle_id !== cycleId || report.owner_user_id !== userId
      || report.status !== 'ready' || report.audience !== 'assessee') throw new Error('REPORT_CONTEXT_MISMATCH');
  const finalExport = await readExecutionExport(page, base, cycleId, runId, evidenceDir);
  if (finalExport.value.pipeline?.status !== 'ready'
      || finalExport.value.report?.id !== report.id
      || finalExport.value.results?.id !== report.results_revision_id
      || finalExport.value.report?.created_by !== userId
      || finalExport.value.pipeline?.latest_report_id !== report.id) {
    throw new Error('REPORT_PIPELINE_READBACK_MISMATCH');
  }
  const screenshot = path.join(evidenceDir, 'available-report.png');
  await page.screenshot({ path: screenshot, fullPage: true });
  stages.push({ stage: 'report_opened', status: 'completed', cycle_id: cycleId,
    report_id: report.id, results_revision_id: report.results_revision_id,
    report_revision_no: report.revision_no, owner_user_id: userId,
    screenshot: path.basename(screenshot), screenshot_sha256: sha256(screenshot) });
  return { contract: 'assessment-execution-contour/2', run_id: runId,
    scope: 'synthetic_technical', cycle_id: cycleId, initial_assessment_situation_id: initialSituationId,
    situation_count: seen.size, report_id: report.id, results_revision_id: report.results_revision_id,
    terminal_export: { file: finalExport.file, sha256: finalExport.sha256 },
    stages, substitutions: ['scripted_participant'], report_opened: true };
}
