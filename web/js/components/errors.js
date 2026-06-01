export const showError = (element, message) => {
  element.hidden = !message;
  element.textContent = message || '';
};
