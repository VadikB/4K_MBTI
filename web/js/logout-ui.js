const getLogoutButtonLabelNode = (button) =>
  button.querySelector('.topbar-exit-button span:last-child') ||
  button.querySelector('span:last-child') ||
  button;

export const applyLogoutButtonPendingState = (button) => {
  if (!(button instanceof HTMLElement)) {
    return () => {};
  }

  const originalDisabled = button.disabled;
  const originalBusy = button.getAttribute('aria-busy');
  const labelNode = getLogoutButtonLabelNode(button);
  const originalLabel = button.dataset.defaultLabel || labelNode.textContent || 'Выйти';
  button.dataset.defaultLabel = originalLabel;

  button.disabled = true;
  button.setAttribute('aria-busy', 'true');
  labelNode.textContent = 'Выходим...';

  return () => {
    button.disabled = originalDisabled;
    if (originalBusy === null) {
      button.removeAttribute('aria-busy');
    } else {
      button.setAttribute('aria-busy', originalBusy);
    }
    labelNode.textContent = originalLabel;
  };
};

export const resetLogoutButtonsState = () => {
  document
    .querySelectorAll(
      '#admin-logout-button, #restart-button, #dashboard-restart-button, #dashboard-mobile-exit-button, #prechat-exit-button, .topbar-exit-button',
    )
    .forEach((button) => {
      if (!(button instanceof HTMLButtonElement)) {
        return;
      }
      const labelNode = getLogoutButtonLabelNode(button);
      const defaultLabel = button.dataset.defaultLabel || 'Выйти';
      button.disabled = false;
      button.removeAttribute('aria-busy');
      labelNode.textContent = defaultLabel;
    });
};
