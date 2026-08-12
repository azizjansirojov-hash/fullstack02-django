/**
 * DOM-level XSS check: flip reader must escape book body so <script> / onerror
 * payloads never execute after client-side pagination/render.
 */
import { execFileSync } from 'child_process'
import path from 'path'

import { expect, test } from '@playwright/test'
import { E2E } from './fixtures'
import { loginViaUi } from './helpers/auth'

const XSS_SLUG = 'e2e-xss-book'
const XSS_BODY = [
  '<script>window.__xss_script=true</script>',
  '<img src=x onerror="window.__xss_img=true">',
  'Plain text with Tom & Jerry.',
].join('\n\n')

function ensureXssBook() {
  const script = `
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
import django
django.setup()
from django.core.files.base import ContentFile
from library.models import Book, BookTranslation
from library.management.commands.seed_e2e import _stub_pdf_bytes, _stub_audio_bytes, _tiny_png

slug = ${JSON.stringify(XSS_SLUG)}
body = ${JSON.stringify(XSS_BODY)}
book, _ = Book.objects.get_or_create(
    slug=slug,
    defaults={
        "author_name": "XSS QA",
        "category": "novel",
        "rights_status": "public_domain",
        "is_published": False,
        "pdf_generation_status": "ready",
        "audio_generation_status": "ready",
    },
)
book.author_name = "XSS QA"
book.rights_status = "public_domain"
book.is_published = False
book.pdf_generation_status = "ready"
book.audio_generation_status = "ready"
if not book.pdf_file:
    book.pdf_file.save(f"{slug}.pdf", ContentFile(_stub_pdf_bytes(1)), save=False)
if not book.audio_file:
    book.audio_file.save(f"{slug}.mp3", ContentFile(_stub_audio_bytes()), save=False)
if not book.cover_image:
    book.cover_image.save(f"{slug}.png", ContentFile(_tiny_png()), save=False)
book.save()
BookTranslation.objects.update_or_create(
    book=book,
    language="uz",
    defaults={
        "title": "E2E XSS Book",
        "summary": "XSS payload book",
        "body": body,
        "why_read": "",
    },
)
book.is_published = True
book.save(update_fields=["is_published"])
print("ok")
`
  execFileSync('python', ['-c', script], {
    cwd: path.resolve(process.cwd(), 'backend'),
    env: process.env,
    encoding: 'utf8',
  })
}

test.describe('flip reader XSS hardening', () => {
  test.beforeAll(() => {
    ensureXssBook()
  })

  test('does not execute script or onerror from book body', async ({ page }) => {
    await loginViaUi(page)

    const dialogs: string[] = []
    page.on('dialog', async (dialog) => {
      dialogs.push(dialog.message())
      await dialog.dismiss()
    })

    await page.goto(`/library/${XSS_SLUG}/read?mode=flip`)
    await expect(page.locator('.flip-reader-view')).toBeVisible({ timeout: 30_000 })
    // Wait for PageFlip pagination to inject page HTML.
    await expect(page.locator('.page-content, .stf__block').first()).toBeVisible({
      timeout: 15_000,
    })

    const flags = await page.evaluate(() => ({
      script: Boolean((window as unknown as { __xss_script?: boolean }).__xss_script),
      img: Boolean((window as unknown as { __xss_img?: boolean }).__xss_img),
    }))
    expect(flags.script).toBe(false)
    expect(flags.img).toBe(false)
    expect(dialogs).toEqual([])

    // Live DOM must not contain an executable script element from the payload.
    const liveScriptCount = await page.locator('.flip-reader-view script').count()
    expect(liveScriptCount).toBe(0)

    // Escaped payload text may appear as text nodes; raw attribute handlers must not.
    const html = await page.locator('.flip-reader-view').innerHTML()
    expect(html).not.toMatch(/<img[^>]+onerror=/i)
    expect(html.toLowerCase()).not.toContain('<script>window.__xss_script')
  })
})
