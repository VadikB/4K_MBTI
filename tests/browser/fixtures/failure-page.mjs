import path from 'node:path';
import { persistReceipt } from './receipt-file.mjs';

export async function captureFailurePage(page, directory, { step, actor }) {
  const url = new URL(page.url());
  const context = await page.evaluate(() => {
    const text = (selector) => document.querySelector(selector)?.textContent?.slice(0, 800) || '';
    const input = document.querySelector('#magic-token-input');
    return { title: text('#auth-title'), status: text('#auth-status'), error: text('#auth-error'),
      credential_step: text('#auth-credential-step-indicator'),
      credential_input: input ? { name: input.name, type: input.type, disabled: input.disabled,
        has_value: input.value.length > 0 } : null };
  });
  const receipt = { step, actor, pathname: url.pathname, query_keys: [...url.searchParams.keys()],
    viewport: page.viewportSize(), ...context, credential_values_exported: false };
  persistReceipt(path.join(directory, 'failure-context.json'), receipt);
  await page.screenshot({ path: path.join(directory, 'failure.png'), fullPage: true,
    mask: [page.locator('#magic-token-input'), page.locator('#auth-password-confirm-input')] });
  return receipt;
}
