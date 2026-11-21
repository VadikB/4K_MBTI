// Use the native modal for focus containment and Escape. Restore the actual invoker.
export const showParticipantDialog = (trigger, { title, body, cancel = 'Закрыть', confirm, confirmAction }) => {
  const existing = document.querySelector('.participant-dialog[open]');
  if (existing) return Promise.resolve(false);
  const dialog = document.createElement('dialog');
  dialog.className = 'participant-dialog';
  dialog.setAttribute('aria-labelledby', 'participant-dialog-title');
  dialog.setAttribute('aria-describedby', 'participant-dialog-body');
  dialog.innerHTML = '<form method="dialog"><h2 id="participant-dialog-title"></h2>' +
    '<div id="participant-dialog-body"></div><div class="participant-dialog-actions">' +
    '<button type="submit" value="cancel" class="ghost-button" autofocus></button></div></form>';
  dialog.querySelector('h2').textContent = title;
  dialog.querySelector('#participant-dialog-body').append(body);
  const cancelButton = dialog.querySelector('button');
  cancelButton.textContent = cancel;
  if (confirm) {
    const button = document.createElement('button');
    button.type = 'submit';
    button.value = 'confirm';
    button.className = 'primary-button';
    button.textContent = confirm;
    dialog.querySelector('.participant-dialog-actions').append(button);
    if (confirmAction) bindConfirmAction(dialog, cancelButton, button, confirmAction);
  }
  document.body.append(dialog);
  return new Promise((resolve) => {
    dialog.addEventListener('close', () => {
      const confirmed = dialog.returnValue === 'confirm';
      dialog.remove();
      if (trigger?.isConnected) trigger.focus({ preventScroll: true });
      resolve(confirmed);
    }, { once: true });
    dialog.showModal();
  });
};

const bindConfirmAction = (dialog, cancelButton, confirmButton, { run, failureMessage }) => {
  const alert = document.createElement('div');
  alert.className = 'participant-dialog-error';
  alert.setAttribute('role', 'alert');
  dialog.querySelector('#participant-dialog-body').append(alert);

  let pending = false;
  dialog.addEventListener('cancel', (event) => {
    if (pending) event.preventDefault();
  });
  dialog.querySelector('form').addEventListener('submit', async (event) => {
    if (pending || event.submitter === confirmButton) event.preventDefault();
    if (pending || event.submitter !== confirmButton) return;

    pending = true;
    cancelButton.disabled = true;
    confirmButton.disabled = true;
    confirmButton.setAttribute('aria-busy', 'true');
    confirmButton.textContent = 'Выходим...';
    alert.textContent = '';
    if (await run()) {
      dialog.close('confirm');
      return;
    }

    pending = false;
    cancelButton.disabled = false;
    confirmButton.disabled = false;
    confirmButton.removeAttribute('aria-busy');
    confirmButton.textContent = 'Повторить';
    alert.textContent = failureMessage;
    confirmButton.focus();
  });
};
