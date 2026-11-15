// One scenario budget shared by every PATH page and imported helper.
const ACTIONS = new Set(['goto', 'reload', 'goBack', 'goForward', 'setContent', 'fill', 'clear', 'type',
  'press', 'insertText', 'click', 'dblclick', 'check', 'uncheck', 'setChecked',
  'selectOption', 'setInputFiles', 'tap', 'hover', 'focus', 'dragTo', 'dispatchEvent']);
const VISUALS = new Set(['newPage', 'bringToFront', 'setViewportSize', 'screenshot',
  'scrollIntoViewIfNeeded', 'wheel', 'move', 'down', 'up']);
const CHILDREN = new Set(['newContext', 'newPage', 'locator', 'getByRole', 'getByText',
  'getByLabel', 'getByPlaceholder', 'getByTestId', 'getByTitle', 'getByAltText',
  'frameLocator', 'frame', 'first', 'last', 'nth', 'filter', 'and', 'or', 'contentFrame']);

export function parsePathBudget({ bounded, actionLimit, visualLimit }) {
  if (!bounded) return null;
  const parse = (value, name) => {
    if (!/^[1-9]\d*$/.test(String(value ?? '')) || !Number.isSafeInteger(Number(value))) {
      throw new Error(`INVALID_${name}`);
    }
    return Number(value);
  };
  return { actions: parse(actionLimit, 'PATH_ACTION_LIMIT'),
    visuals: parse(visualLimit, 'PATH_VISUAL_LIMIT') };
}

export function createPathActionBudget(limits, scope = 'path29-first-case') {
  const valid = parsePathBudget({ bounded: true, actionLimit: limits?.actions,
    visualLimit: limits?.visuals });
  const used = { actions: 0, visuals: 0 };
  let rejected = null, completed = false;
  const cache = new WeakMap();
  const originals = new WeakMap();
  const budget = {
    reserve(kind, operation) {
      if (rejected) throw Object.assign(new Error('PATH_BUDGET_EXCEEDED'), { code: 'PATH_BUDGET_EXCEEDED' });
      if (used[kind] >= valid[kind]) {
        rejected = { kind, operation, reason: 'LIMIT_EXCEEDED' };
        throw Object.assign(new Error('PATH_BUDGET_EXCEEDED'), { code: 'PATH_BUDGET_EXCEEDED' });
      }
      used[kind] += 1;
    },
    finish() { if (!rejected) completed = true; },
    receipt() { return { contract: 'path-action-budget/1', scope, limits: { ...valid },
      used: { ...used }, status: rejected ? 'exceeded' : completed ? 'completed' : 'incomplete',
      rejected: rejected && { ...rejected } }; },
    unwrap(value) { return originals.get(value) || value; },
    wrap(target) {
      if (!target || typeof target !== 'object') return target;
      if (originals.has(target)) return target;
      if (cache.has(target)) return cache.get(target);
      const proxy = new Proxy(target, {
        get(raw, key) {
          const value = Reflect.get(raw, key, raw);
          if (key === 'keyboard' || key === 'mouse' || key === 'touchscreen') return budget.wrap(value);
          if (typeof value !== 'function') return value;
          if (ACTIONS.has(key) || VISUALS.has(key)) {
            return (...args) => {
              budget.reserve(ACTIONS.has(key) ? 'actions' : 'visuals', String(key));
              const result = Reflect.apply(value, raw, args);
              return CHILDREN.has(key) ? Promise.resolve(result).then((child) => budget.wrap(child)) : result;
            };
          }
          if (CHILDREN.has(key)) return (...args) => {
            const result = Reflect.apply(value, raw, args);
            return result instanceof Promise ? result.then((child) => budget.wrap(child)) : budget.wrap(result);
          };
          return value.bind(raw);
        },
      });
      cache.set(target, proxy);
      originals.set(proxy, target);
      return proxy;
    },
  };
  return budget;
}

export function preparePathBrowser(browser, env) {
  const bounded = env.P4K_PATH_BOUNDED === '1';
  const limits = parsePathBudget({ bounded, actionLimit: env.P4K_PATH_ACTION_LIMIT,
    visualLimit: env.P4K_PATH_VISUAL_LIMIT });
  const budget = limits && createPathActionBudget(limits);
  return { browser: budget ? budget.wrap(browser) : browser, budget, bounded };
}
