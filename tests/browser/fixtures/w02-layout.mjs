// Read-only evidence from the actual DOM; never substitutes product content into a reference.
export async function w02Layout(page, reference = false) {
  return page.evaluate((isReference) => {
    const selectors = isReference ? { header: '.product-header', main: '#history', group: '#messages', card: '.status-card', title: '.status-title', section: '#section-name', actions: '.status-card .actions', diagnostics: '.operation-details', tail: '.status-tail', footer: '#footer' }
      : { header: '#onboarding-panel .onboarding-topbar', main: '.onboarding-history', group: '.onboarding-thread', card: '.onboarding-copy > .onboarding-bubble', title: '.onboarding-status-title', section: '.onboarding-section-label', actions: '#onboarding-actions', diagnostics: '.onboarding-copy > .onboarding-bubble > .onboarding-diagnostics', tail: '#onboarding-status-tail', footer: '.app-footer' };
    const describe = (node) => {
      if (!node) return null;
      const r = node.getBoundingClientRect(), s = getComputedStyle(node);
      return { x: r.x, y: r.y, width: r.width, height: r.height, bottom: r.bottom, text: node.innerText,
        display: s.display, margin: s.margin, padding: s.padding, minHeight: s.minHeight, font: s.font, background: s.backgroundColor };
    };
    const result = Object.fromEntries(Object.entries(selectors).map(([k, selector]) => [k, describe(document.querySelector(selector))]));
    const card = document.querySelector(selectors.card);
    result.paragraphs = [...(card?.querySelectorAll('p') || [])].map(describe);
    result.buttons = [...(card?.querySelectorAll('button') || [])].map(describe);
    result.viewport = { width: innerWidth, height: innerHeight, scrollWidth: document.documentElement.scrollWidth, scrollHeight: document.documentElement.scrollHeight, dpr: devicePixelRatio };
    result.shellChildren = [...document.querySelector(isReference ? '#app' : '.shell').children].filter((n) => n.getBoundingClientRect().height > 0).map(describe);
    result.url = location.href; result.fonts = document.fonts.status;
    return result;
  }, reference);
}
