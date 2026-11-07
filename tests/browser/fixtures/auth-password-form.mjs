import { expect } from '@playwright/test';

// Visibility of a token input is not readiness of the validated password form.
export async function waitForPasswordCreationForm(page, email) {
  const input = page.locator('#magic-token-input');
  await expect(page.locator('#auth-token-form')).toBeVisible();
  await expect(input).toHaveAttribute('name', 'new-password');
  await expect(input).toHaveAttribute('autocomplete', 'new-password');
  await expect(input).toHaveAttribute('type', 'password');
  await expect(input).toBeEnabled();
  await expect(page.locator('#auth-credential-email-input')).toHaveValue(email);
  await expect(page.locator('#auth-credential-step-indicator')).toBeVisible();
  await expect(page.locator('#auth-credential-step-indicator')).toHaveText('Шаг 1 из 2');
  await expect(page.locator('#verify-magic-link-button')).toHaveText('Продолжить');
  await expect(page.locator('#verify-magic-link-button')).toBeEnabled();
}
