/** Shared E2E constants — must match seed_e2e management command. */
export const E2E = {
  owner: {
    username: 'e2e_owner',
    password: 'E2e-Passw0rd!Strong',
    email: 'e2e_owner@example.com',
  },
  pdSlug: 'e2e-public-domain',
  licensedSlug: 'e2e-licensed',
  pdTitle: 'E2E Bepul Kitob',
  licensedTitle: 'E2E Pullik Kitob',
  vite: process.env.E2E_VITE_ORIGIN || 'http://127.0.0.1:5173',
  django: process.env.E2E_DJANGO_ORIGIN || 'http://127.0.0.1:8000',
} as const
