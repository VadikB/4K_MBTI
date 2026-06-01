import { messages } from '../dom.js';

export const addMessage = (role, text) => {
  const item = document.createElement('div');
  item.className = 'message ' + role;
  item.textContent = role === 'user' ? String(text ?? '').trim() : text;
  messages.appendChild(item);
  messages.scrollTop = messages.scrollHeight;
};

export const showAgentTyping = () => {
  if (!messages) {
    return;
  }
  hideAgentTyping();
  const item = document.createElement('div');
  item.className = 'message bot message-typing';
  item.id = 'agent-typing-indicator';
  item.setAttribute('aria-label', 'Агент печатает');
  item.setAttribute('role', 'status');
  item.innerHTML =
    '<span class="message-typing-dot"></span>' +
    '<span class="message-typing-dot"></span>' +
    '<span class="message-typing-dot"></span>';
  messages.appendChild(item);
  messages.scrollTop = messages.scrollHeight;
};

export const hideAgentTyping = () => {
  const existing = document.getElementById('agent-typing-indicator');
  if (existing && existing.parentNode) {
    existing.parentNode.removeChild(existing);
  }
};
