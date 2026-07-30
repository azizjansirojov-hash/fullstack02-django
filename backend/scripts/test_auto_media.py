"""One-off E2E check: text-only book -> auto PDF + female Uzbek TTS."""

import os

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from library.generation_utils import GENERATION_READY  # noqa: E402
from library.media_generation import generate_book_media  # noqa: E402
from library.models import Book, BookTranslation  # noqa: E402

Book.objects.filter(slug='auto-test-kitob').delete()

book = Book.objects.create(
    author_name='Test Muallif',
    category=Book.Category.OTHER,
    slug='auto-test-kitob',
    is_published=True,
    published_year=2026,
    rights_status=Book.RightsStatus.LICENSED,
)
BookTranslation.objects.create(
    book=book,
    language=BookTranslation.Language.UZ,
    title='Avtomatik sinov kitobi',
    summary='Qisqa sinov.',
    body=(
        "Salom! Bu avtomatik PDF va audio sinovi.\n\n"
        "Ikkinchi paragraf. O'zbek matni to'g'ri o'qilishi kerak: "
        "kitob, o'qish, g'amxo'rlik.\n\n"
        "Uchinchi paragraf — tinglash rejimi shu matnni aytishi kerak."
    ),
)

print('Generating…')
result = generate_book_media(book)
book.refresh_from_db()
print('result=', result)
print(
    'pdf_status=',
    book.pdf_generation_status,
    'pdf_file=',
    bool(book.pdf_file),
    book.pdf_file.name if book.pdf_file else None,
    'size=',
    book.pdf_file.size if book.pdf_file else 0,
)
print('audio_status=', book.audio_generation_status)
chapters = list(book.audio_chapters.all())
print('chapters=', len(chapters))
for ch in chapters:
    print(
        ' -',
        ch.title,
        ch.voice_id,
        bool(ch.audio_file),
        ch.audio_file.name if ch.audio_file else None,
        'bytes',
        ch.audio_file.size if ch.audio_file else 0,
    )

assert result['pdf'] == GENERATION_READY, result
assert book.pdf_file and book.pdf_file.size > 100, 'PDF missing/too small'
assert result['audio'] == GENERATION_READY, result
assert chapters and chapters[0].audio_file and chapters[0].audio_file.size > 100
assert chapters[0].voice_id == 'uz-UZ-MadinaNeural'

# Legacy skip: second call should not rebuild when hash matches
result2 = generate_book_media(book)
assert result2['pdf'] == GENERATION_READY
assert result2['audio'] == GENERATION_READY
print('E2E OK')
