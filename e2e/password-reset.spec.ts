import { execFileSync } from 'child_process'
import path from 'path'

import { expect, test } from '@playwright/test'

function resetLinkFor(email: string) {
  const script = `
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
import django
django.setup()
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
user = get_user_model().objects.get(email=${JSON.stringify(email)})
print(urlsafe_base64_encode(force_bytes(user.pk)))
print(default_token_generator.make_token(user))
`
  const output = execFileSync('python', ['-c', script], {
    cwd: path.resolve(process.cwd(), 'backend'),
    env: process.env,
    encoding: 'utf8',
  })
  const [uid, token] = output.trim().split(/\r?\n/)
  if (!uid || !token) throw new Error('Could not generate password-reset link.')
  return { uid, token }
}

test('resets a password through the SPA', async ({ page }) => {
  const unique = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
  const username = `reset_${unique}`
  const email = `${username}@example.com`
  const initialPassword = 'Initial-Passw0rd!'
  const newPassword = 'Updated-Passw0rd!'

  await page.goto('/register/')
  await page.locator('#id_username').fill(username)
  await page.locator('#id_email').fill(email)
  await page.locator('#id_password').fill(initialPassword)
  await page.locator('#id_password_confirm').fill(initialPassword)
  await page.getByRole('button', { name: 'Hisob yaratish' }).click()
  await page.waitForURL(/\/library\/?$/)

  await page.goto('/password-reset/')
  await page.locator('#id_email').fill(email)
  await page.getByRole('button', { name: 'Havola yuborish' }).click()
  await expect(page.getByRole('status')).toContainText('reset link has been sent')

  const { uid, token } = resetLinkFor(email)
  await page.goto(`/password-reset/${uid}/${token}/`)
  await page.locator('#id_password').fill(newPassword)
  await page.locator('#id_password_confirm').fill(newPassword)
  await page.getByRole('button', { name: 'Parolni saqlash' }).click()
  // Registration left this browser authenticated. The guest-only login route
  // correctly redirects it to the library after a successful reset.
  await page.waitForURL(/\/library\/?$/)
  await page.context().clearCookies()
  await page.goto('/login/')

  await page.locator('#id_username').fill(username)
  await page.locator('#id_password').fill(newPassword)
  await page.getByRole('button', { name: 'Davom etish' }).click()
  await page.waitForURL(/\/library\/?$/)
})
