// Production dashboard + preparation renderer, minimal DOM and controlled I/O.
// Browser selection/layout are verified separately with the actual bundle.
import fs from 'node:fs';
import vm from 'node:vm';
import { assessmentMetadata, formatAssessmentDate } from '../../../web/js/dashboard-presentation.js';
export const dashboardHarness = () => {
  let document;
  class Element {
    constructor(tag = 'div') { this.tagName = tag.toUpperCase(); this.children = []; this.dataset = {}; this.className = ''; this._text = ''; this.open = false; this.listeners = new Map();
      this.classList = { add() {}, remove() {}, toggle() {} }; }
    get isConnected() { return this === document.body || Boolean(this.parentElement?.isConnected); }
    get textContent() { return this._text + this.children.map(n => n.textContent).join(''); }
    set textContent(v) { this._text = v; this.replaceChildren(); }
    setAttribute(k, v) { if (k === 'class') this.className = v; else if (k.startsWith('data-')) this.dataset[k.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = v; else this[k] = v; }
    hasAttribute(k) { return k.startsWith('data-') ? k.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase()) in this.dataset : k in this; }
    matches(s) { const cls = s.match(/\.([\w-]+)/); const tag = s.match(/^[a-z]+/); const attr = s.match(/\[([^\]]+)\]/); return (!cls || this.className.split(' ').includes(cls[1])) && (!tag || this.tagName === tag[0].toUpperCase()) && (!attr || this.hasAttribute(attr[1])); }
    querySelectorAll(s) { const parts = s.split(' '), found = []; const visit = node => { for (const child of node.children) { if (child.matches(parts[0])) found.push(...(parts.length > 1 ? child.querySelectorAll(parts.slice(1).join(' ')) : [child])); visit(child); } }; visit(this); return found; }
    querySelector(s) { return this.querySelectorAll(s)[0] || null; }
    closest(s) { return this.matches(s) ? this : this.parentElement?.closest(s); }
    appendChild(n) { return this.insertBefore(n, null); }
    insertBefore(n, before) { n.remove(); const index = before ? this.children.indexOf(before) : this.children.length; this.children.splice(index, 0, n); n.parentElement = this; return n; }
    moveBefore(n, before) { this.insertBefore(n, before); }
    append(...nodes) { nodes.forEach(n => this.appendChild(n)); }
    remove() { if (this.parentElement) { this.parentElement.children = this.parentElement.children.filter(n => n !== this); this.parentElement = null; } }
    replaceChildren(...nodes) { for (const n of [...this.children]) n.remove(); this.append(...nodes); }
    focus() { document.activeElement = this; }
    addEventListener(name, cb) { this.listeners.set(name, cb); }
    insertAdjacentHTML(_position, html) {
      const stack = [this];
      for (const token of html.match(/<[^>]+>|[^<]+/g) || []) {
        if (token.startsWith('</')) { stack.pop(); continue; }
        if (token.startsWith('<')) { const node = new Element(token.match(/^<([a-z]+)/)[1]);
          for (const m of token.matchAll(/([\w-]+)(?:="([^"]*)")?/g)) if (m.index > 1) node.setAttribute(m[1], m[2] || '');
          stack.at(-1).append(node); stack.push(node);
        } else stack.at(-1)._text += token;
      }
    }
  }
  document = { createElement: tag => new Element(tag), addEventListener(name, cb) { this[name] = cb; } };
  document.body = new Element('body'); document.activeElement = document.body;
  const context = { document, console, Date, Map, WeakMap, JSON, Number, Boolean, String, encodeURIComponent,
    MutationObserver: class { observe() {} disconnect() {} },
    window: { clearTimeout() {}, setTimeout() { return 1; } }, navigator: { clipboard: { async writeText() {} } },
    state: { pendingUser: { id: '8' }, identityEpoch: 1, currentScreen: 'dashboard', dashboard: {} },
    initAppHeader: () => ({ updateUser() {} }), persistAssessmentContext() {}, assessmentMetadata, formatAssessmentDate,
    readApiResponse: async response => response, fetch: async () => context.response,
    safeStorage: { getItem() {} }, STORAGE_KEYS: {}, hideAllPanels() {}, syncUrlState() {}, setCurrentScreen() {} };
  for (const name of ['dashboardPanel', 'dashboardGreeting', 'currentAssessmentsTitle', 'currentAssessments', 'completedAssessments', 'dashboardRefreshStatus', 'dashboardRefreshButton']) {
    context[name] = new Element(); document.body.append(context[name]);
  }
  context.dashboardPanel.append(context.currentAssessments, context.completedAssessments);
  vm.createContext(context);
  const load = name => fs.readFileSync(new URL('../../../web/js/' + name, import.meta.url), 'utf8').replace(/^import[\s\S]*?from ['"][^'"]+['"];\n/gm, '').replace(/^export /gm, '');
  vm.runInContext(load('preparation-status.js'), context);
  vm.runInContext(load('screens/dashboard.js') + '\nglobalThis.subject = { renderDashboard, refreshDashboard };', context);
  return { context, document, state: context.state, render: context.subject.renderDashboard, refresh: context.subject.refreshDashboard,
    card: id => context.dashboardPanel.querySelectorAll('article').find(n => n.dataset.cycleId === id) };
};
