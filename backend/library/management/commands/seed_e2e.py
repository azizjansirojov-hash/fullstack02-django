"""Seed deterministic books/users for Playwright E2E (idempotent)."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from library.models import AudioChapter, Book, BookTranslation, Purchase, ReadingProgress

User = get_user_model()

E2E_OWNER_USERNAME = 'e2e_owner'
E2E_OWNER_PASSWORD = 'E2e-Passw0rd!Strong'
E2E_OWNER_EMAIL = 'e2e_owner@example.com'
E2E_STAFF_USERNAME = 'e2e_staff'
E2E_STAFF_PASSWORD = 'E2e-Staff-Passw0rd!Strong'
E2E_STAFF_EMAIL = 'e2e_staff@example.com'

E2E_PD_SLUG = 'e2e-public-domain'
E2E_LICENSED_SLUG = 'e2e-licensed'

# Long body so flip pagination yields multiple pages at desktop viewport.
E2E_BODY_PARAGRAPHS = [
    (
        f'Bob {i}. '
        + (
            'Kunlar o‘tib borardi. Yigit shahar ko‘chalarida sekin yurar, '
            'o‘ylari bilan ovora edi. Har bir jumla kitob sahifalarini to‘ldirish '
            'uchun yozilgan matn bo‘lagi hisoblanadi. '
        )
        * 8
    )
    for i in range(1, 16)
]


def _tiny_png() -> bytes:
    import base64

    return base64.b64decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
    )


def _stub_pdf_bytes(pages: int = 3) -> bytes:
    """Small real PDF via reportlab so PDF.js can render canvases in E2E."""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter
    for i in range(1, pages + 1):
        c.setFont('Helvetica', 14)
        c.drawString(72, height - 72, f'E2E PDF page {i}/{pages}')
        c.drawString(72, height - 100, 'Libro.UZ seed_e2e stub document.')
        c.showPage()
    c.save()
    return buf.getvalue()


def _stub_audio_bytes() -> bytes:
    """Playable silent-ish MPEG frames so <audio> can advance currentTime in E2E."""
    fixture = Path(__file__).resolve().parent.parent / 'fixtures' / 'e2e-silence.mp3'
    if fixture.is_file():
        return fixture.read_bytes()
    # MPEG-1 Layer III, 128 kbps, 44100 Hz, stereo — frame length 417.
    header = bytes([0xFF, 0xFB, 0x90, 0x04])
    frame = header + bytes(417 - 4)
    return frame * 120


def seed_e2e_data() -> dict:
    owner, _ = User.objects.get_or_create(
        username=E2E_OWNER_USERNAME,
        defaults={'email': E2E_OWNER_EMAIL},
    )
    owner.email = E2E_OWNER_EMAIL
    owner.set_password(E2E_OWNER_PASSWORD)
    owner.save()

    staff, _ = User.objects.get_or_create(
        username=E2E_STAFF_USERNAME,
        defaults={'email': E2E_STAFF_EMAIL},
    )
    staff.email = E2E_STAFF_EMAIL
    staff.is_staff = True
    staff.is_superuser = True
    staff.set_password(E2E_STAFF_PASSWORD)
    staff.save()

    pdf_bytes = _stub_pdf_bytes(3)
    audio_bytes = _stub_audio_bytes()
    body = '\n\n'.join(E2E_BODY_PARAGRAPHS)

    def make_book(slug: str, rights: str, title: str) -> Book:
        book, _ = Book.objects.get_or_create(
            slug=slug,
            defaults={
                'author_name': 'E2E Author',
                'category': Book.Category.NOVEL,
                'rights_status': rights,
                'is_published': False,
                'pdf_generation_status': 'ready',
                'audio_generation_status': 'ready',
            },
        )
        book.author_name = 'E2E Author'
        book.category = Book.Category.NOVEL
        book.rights_status = rights
        book.pdf_generation_status = 'ready'
        book.audio_generation_status = 'ready'
        book.pdf_file.save(f'{slug}.pdf', ContentFile(pdf_bytes), save=False)
        if not book.cover_image:
            book.cover_image.save(f'{slug}.png', ContentFile(_tiny_png()), save=False)
        book.audio_file.save(f'{slug}.mp3', ContentFile(audio_bytes), save=False)
        book.save()

        BookTranslation.objects.update_or_create(
            book=book,
            language=BookTranslation.Language.UZ,
            defaults={
                'title': title,
                'summary': f'E2E summary for {slug}',
                'body': body,
                'why_read': 'E2E why read.',
                'audio_sync': [
                    {'start': 0.0, 'end': 2.0, 'index': 0, 'text': 'Bob 1.'},
                    {'start': 2.0, 'end': 4.0, 'index': 1, 'text': 'Davom.'},
                ],
            },
        )

        chapter, _ = AudioChapter.objects.get_or_create(
            book=book,
            order=0,
            defaults={'title': '1-qism', 'duration_seconds': 12},
        )
        chapter.title = '1-qism'
        chapter.duration_seconds = 12
        chapter.audio_file.save(f'{slug}-ch0.mp3', ContentFile(audio_bytes), save=False)
        chapter.save()

        book.is_published = True
        book.save()
        return book

    pd = make_book(E2E_PD_SLUG, Book.RightsStatus.PUBLIC_DOMAIN, 'E2E Bepul Kitob')
    licensed = make_book(E2E_LICENSED_SLUG, Book.RightsStatus.LICENSED, 'E2E Pullik Kitob')

    # Owner has NO purchase on licensed book by default (blocked-access tests).
    Purchase.objects.filter(user=owner, book=licensed).delete()
    # Clean progress so reader reload tests start from a known state.
    ReadingProgress.objects.filter(user=owner, book__in=[pd, licensed]).delete()

    return {
        'owner': owner,
        'password': E2E_OWNER_PASSWORD,
        'pd': pd,
        'licensed': licensed,
    }


class Command(BaseCommand):
    help = 'Seed idempotent public-domain + licensed books and e2e_owner for Playwright.'

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                'seed_e2e refuses to run when DEBUG=False. This command creates a '
                'user with a hardcoded, publicly-known password and must only be '
                'run in local/CI environments (DEBUG=True). Refusing to continue.'
            )
        data = seed_e2e_data()
        self.stdout.write(
            self.style.SUCCESS(
                f"seed_e2e ok owner={data['owner'].username} "
                f"staff={E2E_STAFF_USERNAME} "
                f"pd={data['pd'].slug} licensed={data['licensed'].slug}"
            )
        )
