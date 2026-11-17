// Mutable input only. No presence, Turn, provider, or automatic answer retry.
export const DRAFT_DEBOUNCE_MS = 750;
export const DRAFT_MAX_WAIT_MS = 3000;
const PREFIX = 'agent4k.answerDraft:v1:';
export const pruneExpiredDrafts = (storage = window.localStorage) => {
  for (const key of storage.keys?.() || Object.keys(storage)) {
    if (!key.startsWith(PREFIX) && !key.startsWith('agent4k.assessmentPending:')) continue;
    try {
      const saved = JSON.parse(storage.getItem(key));
      const expiry = saved?.expiresAt;
      if (expiry && (typeof expiry === 'number' ? expiry : Date.parse(expiry)) <= Date.now()) storage.removeItem(key);
    } catch { /* no adoption of malformed input */ }
  }
};
export const draftSlot = (snapshot) => {
  const question = snapshot?.clarification;
  if (question?.status === 'ASK' && !question.response_outcome && question.question_turn_id) {
    return `clarification:${question.id}:${question.question_turn_id}`;
  }
  const turns = snapshot?.trace?.turns || [];
  const last = turns.reduce((a, b) => !a || b.sequence_no > a.sequence_no ? b : a, null);
  return 'dialogue:' + (last?.turn_id || 'start');
};

export const clearOwnerDrafts = (ownerId, storage = window.localStorage) => {
  for (const key of Object.keys(storage)) {
    if (key.startsWith(PREFIX + ownerId + ':') || (key.startsWith('agent4k.assessmentPending:')
        && (key.endsWith(':' + ownerId) || key.includes(':' + ownerId + ':resolved:')))) storage.removeItem(key);
  }
};

export const hasUnconfirmedDrafts = (ownerId, storage = window.localStorage) => Object.keys(storage)
  .some((key) => {
    if (!key.startsWith(PREFIX + ownerId + ':')) return false;
    try { const record = JSON.parse(storage.getItem(key)); return record?.confirmed === false || Boolean(record?.alternatives?.length); } catch { return true; }
  });

export const createAnswerDrafts = ({ input, status, actions, request, current,
  onConflictChange = () => {}, storage = window.localStorage, timers = window, newRevision = () => crypto.randomUUID() }) => {
  const editorId = newRevision();
  let active = null, timer = null, maxTimer = null;
  const cancelTimers = () => { timers.clearTimeout(timer); timers.clearTimeout(maxTimer); timer = maxTimer = null; };
  const valid = (entry) => entry === active && current(entry.scope);
  const message = (entry, text) => { if (valid(entry)) status.textContent = text; };
  const persist = (entry) => {
    try { storage.setItem(entry.key, JSON.stringify(entry.record)); entry.local = true; }
    catch { entry.local = false; }
  };
  const unsaved = (entry) => message(entry, entry.local
    ? 'Сохранено на этом устройстве. Синхронизируем при восстановлении связи'
    : 'Не удалось сохранить черновик. Не закрывайте страницу, пока не скопируете текст');
  const conflict = (entry) => {
    if (!valid(entry)) return;
    entry.conflict = true; cancelTimers();
    onConflictChange(true);
    message(entry, 'В другой вкладке или на другом устройстве сохранён другой вариант черновика. Выберите, с каким текстом продолжить');
    actions.replaceChildren();
    for (const [label, keepLocal] of [['Оставить текст из этой вкладки', true], ['Использовать другой сохранённый вариант', false]]) {
      const button = document.createElement('button'); button.type = 'button'; button.className = 'text-button';
      button.textContent = label;
      button.addEventListener('click', async () => {
        button.disabled = true;
        try {
          const remote = await request(entry.scope, null);
          if (!valid(entry) || remote.slot_id !== entry.scope.slotId) return;
          entry.record.baseVersion = remote.version; entry.record.baseRevision = remote.revision;
          if (!keepLocal) {
            input.value = remote.text; entry.record.text = remote.text;
            entry.record.revision = remote.revision; entry.record.confirmed = true;
          } else { entry.record.revision = newRevision(); entry.record.confirmed = false; }
          delete entry.record.alternatives; entry.record.editorId = editorId;
          entry.conflict = false; entry.ready = true; onConflictChange(false);
          persist(entry); actions.replaceChildren(); input.dataset.draftRevision = entry.record.revision;
          if (keepLocal) await flush(); else message(entry, 'Черновик восстановлен. Ответ ещё не отправлен');
        } catch { if (valid(entry)) { button.disabled = false; conflict(entry); } }
      }); actions.append(button);
    }
    for (const alternative of entry.record.alternatives || []) {
      const button = document.createElement('button'); button.type = 'button'; button.className = 'text-button';
      button.textContent = 'Восстановить текст другой вкладки';
      button.addEventListener('click', () => {
        const previous = { text: entry.record.text, revision: entry.record.revision };
        input.value = alternative.text; entry.record.text = alternative.text; entry.record.revision = newRevision();
        input.dataset.draftRevision = entry.record.revision;
        entry.record.alternatives = [...entry.record.alternatives.filter(a => a !== alternative), previous]; persist(entry); conflict(entry);
      }); actions.append(button);
    }
  };
  const schedule = () => {
    timers.clearTimeout(timer); timer = timers.setTimeout(() => void flush(), DRAFT_DEBOUNCE_MS);
    if (!maxTimer) maxTimer = timers.setTimeout(() => void flush(), DRAFT_MAX_WAIT_MS);
  };
  const flush = async () => {
    const entry = active; cancelTimers();
    if (entry?.suspended) return;
    if (entry && valid(entry) && !entry.ready && !entry.record.confirmed) { unsaved(entry); return; }
    if (!entry || !valid(entry) || entry.suspended || !entry.ready || entry.conflict || entry.inflight || entry.record.confirmed) return;
    const sent = { ...entry.record }; entry.inflight = true;
    message(entry, 'Сохраняем черновик…');
    try {
      const remote = await request(entry.scope, { slot_id: entry.scope.slotId,
        expected_version: sent.baseVersion, revision: sent.revision, text: sent.text });
      if (!valid(entry) || entry.stopped) return;
      if (remote.slot_id !== entry.scope.slotId || remote.revision !== sent.revision || remote.text !== sent.text) throw new Error('DRAFT_ACK_MISMATCH');
      entry.record.baseVersion = remote.version; entry.record.baseRevision = remote.revision;
      entry.record.confirmed = entry.record.revision === sent.revision;
      // A response from this tab must not overwrite a divergent local buffer.
      let stored; try { stored = JSON.parse(storage.getItem(entry.key)); } catch { /* status below */ }
      if (stored && ![sent.revision, entry.record.revision].includes(stored.revision)) { conflict(entry); return; }
      persist(entry);
      if (entry.record.confirmed) message(entry, 'Черновик сохранён'); else schedule();
    } catch (error) {
      if (!valid(entry) || entry.stopped) return;
      if (Number(error?.status) === 409 && /DRAFT_UNAVAILABLE|DRAFT_SLOT_CHANGED|M7_/.test(String(error.code || error.message))) {
        entry.suspended = true;
        message(entry, 'Прежний черновик. Отправка сейчас недоступна; текст можно скопировать');
      } else if (Number(error?.status) === 409) conflict(entry); else unsaved(entry);
    } finally { entry.inflight = false; }
  };
  const bind = (scope, { readOnly = false, fallbackText = '', fallbackRevision = '' } = {}) => {
    try { pruneExpiredDrafts(storage); } catch { /* remote remains available */ }
    const key = PREFIX + scope.ownerId + ':' + scope.cycleId + ':' + scope.situationId + ':' + scope.slotId;
    if (active?.key === key && active.scope.identityEpoch === scope.identityEpoch) { active.suspended = readOnly; return; }
    cancelTimers(); input.value = ''; input.dataset.draftRevision = ''; status.textContent = ''; actions.replaceChildren();
    const entry = { scope, key, ready: false, local: false, record: {
      text: '', revision: '', baseVersion: null, baseRevision: '', confirmed: true } }; active = entry;
    try {
      const saved = JSON.parse(storage.getItem(key) || 'null');
      if (saved && typeof saved.text === 'string' && saved.text.length <= 10000 && saved.expiresAt > Date.now()) {
        entry.record = saved; entry.local = true; input.value = saved.text;
        input.dataset.draftRevision = saved.revision;
        if (saved.text) message(entry, 'Черновик восстановлен. Ответ ещё не отправлен');
      } else if (saved) storage.removeItem(key);
    } catch { /* remote can still restore/safely save without local storage */ }
    if (readOnly) {
      entry.suspended = true;
      if (!entry.record.revision) {
        entry.record.text = fallbackText; entry.record.revision = fallbackRevision; entry.record.confirmed = false;
        input.value = fallbackText; input.dataset.draftRevision = fallbackRevision;
      }
      message(entry, 'Исход отправки пока не подтверждён. Прежний текст можно скопировать');
      const copy = document.createElement('button'); copy.type = 'button'; copy.className = 'text-button';
      copy.textContent = 'Скопировать текст';
      copy.addEventListener('click', async () => {
        try {
          if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(input.value);
          else {
            const selection = document.createElement('textarea'); selection.value = input.value;
            selection.readOnly = true; document.body.append(selection); selection.select();
            try { if (!document.execCommand('copy')) throw new Error('COPY_UNAVAILABLE'); }
            finally { selection.remove(); }
          }
        } catch { message(entry, 'Не удалось скопировать. Выделите и скопируйте текст вручную'); }
      }); actions.append(copy);
      return;
    }
    restoreRemote(entry);
  };
  const restoreRemote = (entry) => {
    const scope = entry.scope;
    void request(scope, null).then((remote) => {
      if (!valid(entry) || entry.stopped || remote.slot_id !== scope.slotId
          || remote.owner_id !== scope.ownerId || remote.cycle_id !== scope.cycleId
          || remote.assessment_situation_id !== scope.situationId) return;
      entry.ready = true;
      if (entry.conflict || entry.record.alternatives?.length) { conflict(entry); return; }
      if (!entry.record.confirmed && entry.record.revision !== remote.revision
          && entry.record.baseVersion !== remote.version
          && !(entry.record.baseVersion === null && remote.version === 0)) { conflict(entry); return; }
      if (entry.record.confirmed) {
        entry.record.text = remote.text; entry.record.revision = remote.revision;
        input.value = remote.text; input.dataset.draftRevision = remote.revision;
      }
      entry.record.baseVersion = remote.version; entry.record.baseRevision = remote.revision;
      entry.record.expiresAt = Date.parse(remote.expires_at);
      if (entry.record.revision === remote.revision && entry.record.text === remote.text) entry.record.confirmed = true;
      persist(entry);
      if (entry.record.confirmed) {
        if (remote.text) message(entry, 'Черновик восстановлен. Ответ ещё не отправлен');
      } else void flush();
    }).catch(() => { if (valid(entry) && entry.record.text) unsaved(entry); });
  };
  const edit = () => {
    const entry = active; if (!entry || !valid(entry) || entry.stopped) return;
    let stored; try { stored = JSON.parse(storage.getItem(entry.key)); } catch { /* preserve DOM */ }
    if (stored && (stored.revision !== entry.record.revision
        || (!stored.confirmed && stored.editorId !== editorId))) {
      const alternatives = [...(entry.record.alternatives || []), ...(stored.alternatives || []),
        { text: stored.text, revision: stored.revision }];
      entry.record.alternatives = [...new Map(alternatives.map(a => [a.revision, a])).values()]
        .filter(a => a.text !== input.value);
      entry.conflict = true;
    }
    entry.record.text = input.value; entry.record.revision = newRevision(); entry.record.confirmed = false;
    entry.record.editorId = editorId;
    // Unconfirmed-runtime local records expire with the known fixed Cycle window.
    entry.record.expiresAt ||= scopeExpiry(entry.scope);
    input.dataset.draftRevision = entry.record.revision; persist(entry);
    if (entry.conflict) conflict(entry); else { message(entry, 'Сохраняем черновик…'); schedule(); }
  };
  const clearAccepted = (operation) => {
    if (!operation?.draftSlotId) return;
    if (operation.accepted && operation.draftRevision) {
      void request({ ...operation, slotId: operation.draftSlotId }, { accepted: true,
        slot_id: operation.draftSlotId, revision: operation.draftRevision,
        request_id: operation.requestId, turn_id: operation.turnId,
        clarification_id: operation.clarificationId }).catch(() => { /* stale slots cannot be saved/restored */ });
    }
    const key = PREFIX + operation.ownerId + ':' + operation.cycleId + ':' + operation.situationId + ':' + operation.draftSlotId;
    try {
      const saved = JSON.parse(storage.getItem(key) || 'null');
      if (saved?.revision === operation.draftRevision) storage.removeItem(key);
    } catch { /* never erase a newer DOM revision */ }
    if (active?.key === key && valid(active) && active.record.revision === operation.draftRevision) {
      active.stopped = true; cancelTimers(); input.value = ''; input.dataset.draftRevision = '';
      active.record.text = ''; active.record.confirmed = true; message(active, 'Ответ принят'); actions.replaceChildren();
    }
  };
  const stop = () => { cancelTimers(); if (active) active.stopped = true; active = null;
    input.value = ''; input.dataset.draftRevision = ''; status.textContent = ''; actions.replaceChildren(); };
  const storageChanged = (event) => {
    if (!active || event.key !== active.key || !valid(active)) return;
    if (event.newValue === null) {
      // Explicit logout/accepted clearing in a sibling tab fences late ACKs;
      // those responses must never recreate a removed local copy.
      active.suspended = true; active.stopped = true; cancelTimers(); return;
    }
    try { if (event.newValue && JSON.parse(event.newValue)?.revision !== active.record.revision) conflict(active); }
    catch { conflict(active); }
  };
  const retry = () => { if (!active || active.suspended || active.conflict) return;
    if (!active.ready || active.record.confirmed) restoreRemote(active); else void flush(); };
  return { bind, edit, flush, clearAccepted, stop, retry, storageChanged,
    restorePending: (operation) => bind({ ...operation, slotId: operation.draftSlotId || 'pending:' + operation.requestId },
      { readOnly: true, fallbackText: operation.draftValue, fallbackRevision: operation.draftRevision || operation.requestId }),
    suspend: () => { cancelTimers(); if (active) { active.suspended = true;
      if (active.record.text) message(active, 'Прежний черновик. Отправка сейчас недоступна; текст можно скопировать'); } },
    saved: () => Boolean(active && valid(active) && (active.local || (active.ready && active.record.confirmed))),
    unsynced: () => Boolean(active && !active.record.confirmed),
    conflicted: () => Boolean(active && valid(active) && active.conflict),
    revision: () => active?.record.revision || '', slotId: () => active?.scope.slotId || '' };
};

const scopeExpiry = (scope) => Date.parse(scope.expiresAt) || Date.now();
