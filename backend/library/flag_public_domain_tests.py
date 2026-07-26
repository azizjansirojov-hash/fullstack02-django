"""Tests for flag_public_domain_classics management command."""

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from .models import Book, BookTranslation


class FlagPublicDomainClassicsTests(TestCase):
    def test_flags_dostoevsky_licensed_book(self):
        book = Book.objects.create(
            author_name='Fyodor Dostoyevskiy Mixaylovich',
            slug='jinoyat-cmd',
            is_published=True,
            rights_status=Book.RightsStatus.LICENSED,
            pdf_generation_status='ready',
            audio_generation_status='ready',
        )
        BookTranslation.objects.create(
            book=book,
            language=BookTranslation.Language.UZ,
            title='Jinoyat va jazo',
            body='Matn.',
        )
        other = Book.objects.create(
            author_name='Modern Writer',
            slug='modern-cmd',
            rights_status=Book.RightsStatus.LICENSED,
        )
        BookTranslation.objects.create(
            book=other,
            language=BookTranslation.Language.UZ,
            title='Yangi roman',
            body='Matn.',
        )

        out = StringIO()
        call_command('flag_public_domain_classics', stdout=out)
        book.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(book.rights_status, Book.RightsStatus.PUBLIC_DOMAIN)
        self.assertEqual(other.rights_status, Book.RightsStatus.LICENSED)
        self.assertIn('Updated 1', out.getvalue())
