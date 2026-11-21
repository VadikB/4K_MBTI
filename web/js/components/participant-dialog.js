// Use the native modal for focus containment and Escape. Restore the actual invoker.
export const showParticipantDialog = (trigger, { title, body, cancel = 'Закрыть', confirm, describeContents = true }) => {
  const existing = document.querySelector('.participant-dialog[open]');
  if (existing) return Promise.resolve(false);
  const dialog = document.createElement('dialog');
  dialog.className = 'participant-dialog';
  dialog.setAttribute('aria-labelledby', 'participant-dialog-title');
  if (describeContents) dialog.setAttribute('aria-describedby', 'participant-dialog-body');
  dialog.innerHTML = '<form method="dialog"><h2 id="participant-dialog-title"></h2>' +
    '<div id="participant-dialog-body"></div><div class="participant-dialog-actions">' +
    '<button type="submit" value="cancel" class="ghost-button" autofocus></button></div></form>';
  dialog.querySelector('h2').textContent = title;
  dialog.querySelector('#participant-dialog-body').append(body);
  dialog.querySelector('button').textContent = cancel;
  if (confirm) {
    const button = document.createElement('button');
    button.type = 'submit';
    button.value = 'confirm';
    button.className = 'primary-button';
    button.textContent = confirm;
    dialog.querySelector('.participant-dialog-actions').append(button);
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
