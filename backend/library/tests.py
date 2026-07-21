"""Tests for the Uzbek-only library catalog and reader."""

import json

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import Book, BookTranslation

User = get_user_model()


class LibraryViewsTests(TestCase):
    def setUp(self):
        self.book = Book.objects.create(
            author_name='Ada Lovelace',
            category=Book.Category.SCIENCE,
            published_year=1843,
            is_published=False,
            slug='notes-on-the-analytical-engine',
        )
        BookTranslation.objects.create(
            book=self.book,
            language=BookTranslation.Language.UZ,
            title='Analitik mashina haqida eslatmalar',
            summary='Hisoblash va tasavvur asoslari.',
            why_read='Dasturlanadigan mashinalar nima uchun muhimligini bilish uchun o‘qing.',
            body='O‘zbekcha birinchi bob.\n\nO‘zbekcha ikkinchi bob.',
        )
        self.book.is_published = True
        self.book.save()

        self.fantasy = Book.objects.create(
            author_name='Story Weaver',
            category=Book.Category.FANTASY,
            slug='ember-crown',
            is_published=True,
        )
        BookTranslation.objects.create(
            book=self.fantasy,
            language=BookTranslation.Language.UZ,
            title='Olov toji',
            summary='Fantaziya.',
            why_read='Hayrat uchun.',
            body='Bir paytlar olov.',
        )

        self.reader = User.objects.create_user(
            username='reader',
            password='testpass123',
        )

    def test_empty_catalog_when_unpublished(self):
        Book.objects.update(is_published=False)
        response = self.client.get(reverse('library:catalog'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No books yet')
        self.assertContains(response, 'Shelves')
        self.assertNotContains(response, 'lang-switch')

    def test_guests_can_observe_catalog_without_language_ui(self):
        response = self.client.get(reverse('library:catalog'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Analitik mashina haqida eslatmalar')
        self.assertContains(response, 'Ada Lovelace')
        self.assertContains(response, 'Sign in to read')
        self.assertContains(response, 'Browse freely')
        self.assertContains(response, 'shelves-toggle')
        self.assertContains(response, 'library-search--compact')
        self.assertContains(response, 'shelves-panel')
        self.assertNotContains(response, 'EN · RU · UZ')
        self.assertNotContains(response, 'lang-switch')
        content = response.content.decode()
        self.assertNotIn('aria-label="Card language"', content)
        # Topics stay hidden until Shelves is opened (no active category).
        self.assertIn('id="shelves-panel"', content)
        self.assertIn('hidden', content[content.find('id="shelves-panel"') :][:120])

    def test_category_filter_keeps_directions_separate(self):
        response = self.client.get(
            reverse('library:catalog'),
            {'category': Book.Category.SCIENCE},
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        grid_start = content.find('class="shelf-grid"')
        grid_end = content.find('</ul>', grid_start)
        shelf_grid = content[grid_start:grid_end]
        self.assertIn('Analitik mashina haqida eslatmalar', shelf_grid)
        self.assertNotIn('Olov toji', shelf_grid)
        self.assertContains(response, 'Showing')
        self.assertContains(response, 'Science')
        panel_tag = content[content.find('id="shelves-panel"') :].split('>')[0]
        self.assertIn('is-open', panel_tag)
        self.assertNotIn('hidden', panel_tag)
        # Topics still list fantasy titles inside the open shelves panel.
        self.assertContains(response, 'Olov toji')

    def test_search_finds_title(self):
        response = self.client.get(
            reverse('library:catalog'),
            {'q': 'Olov'},
        )
        content = response.content.decode()
        grid_start = content.find('class="shelf-grid"')
        grid_end = content.find('</ul>', grid_start)
        shelf_grid = content[grid_start:grid_end]
        self.assertIn('Olov toji', shelf_grid)
        self.assertNotIn('Analitik mashina haqida eslatmalar', shelf_grid)

    def test_guests_cannot_open_reader(self):
        url = reverse('library:book-detail', kwargs={'slug': self.book.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('users:login'), response.url)
        self.assertIn('next=', response.url)

        read_url = reverse('library:book-read', kwargs={'slug': self.book.slug})
        read_response = self.client.get(read_url)
        self.assertEqual(read_response.status_code, 302)
        self.assertIn(reverse('users:login'), read_response.url)

    def test_registered_user_can_read_uzbek_content(self):
        self.client.login(username='reader', password='testpass123')
        url = reverse('library:book-detail', kwargs={'slug': self.book.slug})

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'O‘zbekcha birinchi bob')
        self.assertContains(response, 'Science')
        self.assertContains(response, 'Continue Reading')
        self.assertContains(response, 'Download PDF')
        self.assertContains(response, 'reading-mode-selector-detail')
        self.assertContains(response, 'reader-progress')
        self.assertContains(response, 'reader-hero')
        self.assertNotContains(response, 'reader-body')
        self.assertNotContains(response, 'book-reader')
        self.assertNotContains(response, 'reader-mode')
        self.assertNotContains(response, 'lang-switch')
        self.assertNotContains(response, '?lang=')

    def test_catalog_opens_immersive_reader_for_signed_in_users(self):
        self.client.login(username='reader', password='testpass123')
        response = self.client.get(reverse('library:catalog'))
        self.assertContains(
            response,
            reverse('library:book-read', kwargs={'slug': self.book.slug}),
        )
        self.assertNotContains(
            response,
            f'href="{reverse("library:book-detail", kwargs={"slug": self.book.slug})}"',
        )
        self.assertContains(response, 'id="reader-launch-modal"')
        self.assertContains(response, 'data-launch-modal="true"')
        self.assertContains(response, 'id="launch-read"')
        self.assertContains(response, 'id="launch-listen"')
        self.assertContains(response, 'O‘QISH USULLARI')
        self.assertContains(response, 'KITOB HAQIDA')

    def test_immersive_reader_opens_on_read_url(self):
        self.client.login(username='reader', password='testpass123')
        url = reverse('library:book-read', kwargs={'slug': self.book.slug})

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'O‘zbekcha birinchi bob')
        self.assertNotContains(response, 'Why read this book')
        self.assertContains(response, 'book-reader')
        self.assertContains(response, 'book-reader__toolbar-shell')
        self.assertNotContains(response, '<nav class="book-reader__toolbar"')
        self.assertNotContains(response, 'id="btn-prev"')
        self.assertContains(response, 'book-counter')
        self.assertContains(response, 'reader-mode')
        self.assertContains(response, 'reader-toolbar-root')
        self.assertContains(response, 'pdf-reader')
        self.assertContains(response, 'reader-orchestrator.js')

    def test_unpublished_book_not_readable(self):
        self.client.login(username='reader', password='testpass123')
        self.book.is_published = False
        self.book.save(update_fields=['is_published'])
        url = reverse('library:book-detail', kwargs={'slug': self.book.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_login_redirects_to_library(self):
        response = self.client.post(
            reverse('users:api-login'),
            data={'username': 'reader', 'password': 'testpass123'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['redirect_url'], reverse('library:catalog'))

    def test_login_honors_next_book_url(self):
        next_url = reverse('library:book-detail', kwargs={'slug': self.book.slug})
        response = self.client.post(
            reverse('users:api-login'),
            data={
                'username': 'reader',
                'password': 'testpass123',
                'next': next_url,
            },
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['redirect_url'], next_url)


class BookModelTests(TestCase):
    def test_publish_requires_uzbek_translation_on_save(self):
        book = Book.objects.create(
            author_name='No Content',
            slug='no-content-yet',
            is_published=False,
        )
        book.is_published = True
        with self.assertRaises(ValidationError):
            book.save()

    def test_audio_sync_must_be_array(self):
        book = Book.objects.create(author_name='Sync', slug='sync-book')
        translation = BookTranslation(
            book=book,
            title='Sync Test',
            body='Body.',
            audio_sync={'start': 0, 'end': 1},
        )
        with self.assertRaises(ValidationError):
            translation.full_clean()

    def test_audio_sync_row_requires_numeric_timing(self):
        book = Book.objects.create(author_name='Sync', slug='sync-book-2')
        translation = BookTranslation(
            book=book,
            title='Sync Test',
            body='Body.',
            audio_sync=[{'start': '0', 'end': 1}],
        )
        with self.assertRaises(ValidationError):
            translation.full_clean()


class LibraryReaderTests(TestCase):
    def setUp(self):
        self.reader = User.objects.create_user(
            username='reader',
            password='testpass123',
        )
        self.book = Book.objects.create(
            author_name='Reader Author',
            slug='reader-test-book',
            is_published=False,
        )
        self.translation = BookTranslation.objects.create(
            book=self.book,
            title='Reader Test',
            body='First sentence. Second sentence.',
            audio_sync=[
                {'index': 0, 'text': 'First sentence.', 'start': 0.0, 'end': 2.5},
                {'index': 1, 'text': 'Second sentence.', 'start': 2.5, 'end': 5.0},
            ],
        )
        self.book.is_published = True
        self.book.save()

    def test_reader_embeds_audio_sync_via_json_script(self):
        self.client.login(username='reader', password='testpass123')
        url = reverse('library:book-read', kwargs={'slug': self.book.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="audio-sync-data"')
        self.assertNotContains(response, 'data-audio-sync=')
        content = response.content.decode()
        script_start = content.find('id="audio-sync-data"')
        script_chunk = content[script_start : script_start + 500]
        json_start = script_chunk.find('>') + 1
        json_end = script_chunk.find('</script>')
        parsed = json.loads(script_chunk[json_start:json_end])
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]['start'], 0.0)

    def test_detail_hides_continue_reading_when_body_empty(self):
        empty_book = Book.objects.create(
            author_name='Empty Body',
            slug='empty-body-book',
            is_published=False,
        )
        BookTranslation.objects.create(
            book=empty_book,
            title='Empty Body Title',
            body='',
        )
        empty_book.is_published = True
        empty_book.save()

        self.client.login(username='reader', password='testpass123')
        url = reverse('library:book-detail', kwargs={'slug': empty_book.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Continue Reading')
        self.assertContains(response, 'Readable content is not available yet')

    def test_catalog_excludes_books_without_body(self):
        empty_book = Book.objects.create(
            author_name='Empty Shelf',
            slug='empty-shelf-book',
            is_published=False,
        )
        BookTranslation.objects.create(
            book=empty_book,
            title='Should Not Appear',
            body='',
        )
        empty_book.is_published = True
        empty_book.save()

        response = self.client.get(reverse('library:catalog'))
        self.assertNotContains(response, 'Should Not Appear')
