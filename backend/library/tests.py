"""Tests for the Uzbek-only library catalog redirects and reader."""

import json

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import AudioChapter, Book, BookTranslation, Purchase
from .spa_urls import spa_book_detail_url, spa_library_home_url

User = get_user_model()


class LibraryViewsTests(TestCase):
    def setUp(self):
        self.book = Book.objects.create(
            author_name='Ada Lovelace',
            category=Book.Category.SCIENCE,
            published_year=1843,
            is_published=True,
            rights_status=Book.RightsStatus.LICENSED,
            slug='notes-on-the-analytical-engine',
            pdf_generation_status='ready',
            audio_generation_status='ready',
        )
        BookTranslation.objects.create(
            book=self.book,
            language=BookTranslation.Language.UZ,
            title='Analitik mashina haqida eslatmalar',
            summary='Hisoblash va tasavvur asoslari.',
            why_read='Dasturlanadigan mashinalar nima uchun muhimligini bilish uchun o‘qing.',
            body='O‘zbekcha birinchi bob.\n\nO‘zbekcha ikkinchi bob.',
        )

        self.fantasy = Book.objects.create(
            author_name='Story Weaver',
            category=Book.Category.FANTASY,
            slug='ember-crown',
            is_published=True,
            rights_status=Book.RightsStatus.LICENSED,
            pdf_generation_status='ready',
            audio_generation_status='ready',
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
        Purchase.objects.create(
            user=self.reader,
            book=self.book,
            status=Purchase.Status.PAID,
        )
        Purchase.objects.create(
            user=self.reader,
            book=self.fantasy,
            status=Purchase.Status.PAID,
        )

    def test_catalog_url_redirects_to_spa_home(self):
        response = self.client.get(reverse('library:catalog'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, spa_library_home_url())

    def test_catalog_url_name_still_reverses(self):
        self.assertEqual(reverse('library:catalog'), '/library/')

    def test_book_detail_url_redirects_to_spa(self):
        response = self.client.get(
            reverse('library:book-detail', kwargs={'slug': self.book.slug})
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, spa_book_detail_url(self.book.slug))

    def test_guests_cannot_open_reader(self):
        read_url = reverse('library:book-read', kwargs={'slug': self.book.slug})
        read_response = self.client.get(read_url)
        self.assertEqual(read_response.status_code, 302)
        self.assertIn(reverse('users:login'), read_response.url)

    def test_registered_user_detail_redirects_to_spa(self):
        self.client.login(username='reader', password='testpass123')
        url = reverse('library:book-detail', kwargs={'slug': self.book.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, spa_book_detail_url(self.book.slug))

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
        self.assertContains(response, spa_library_home_url())

    def test_reader_accepts_jwt_cookie_without_session(self):
        """JWT-only clients (expired Django session) can still open the reader."""
        from django.conf import settings

        from users.auth import get_tokens_for_user

        tokens = get_tokens_for_user(self.reader)
        self.client.cookies[settings.JWT_ACCESS_COOKIE_NAME] = tokens['access']
        # Ensure no Django session auth is present.
        session = self.client.session
        session.flush()

        url = reverse('library:book-read', kwargs={'slug': self.book.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'book-reader')

    def test_unpublished_book_detail_not_found(self):
        self.client.login(username='reader', password='testpass123')
        Book.objects.filter(pk=self.book.pk).update(is_published=False)
        url = reverse('library:book-detail', kwargs={'slug': self.book.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_login_redirects_to_spa_library(self):
        response = self.client.post(
            reverse('users:api-login'),
            data={'username': 'reader', 'password': 'testpass123'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['redirect_url'], spa_library_home_url())

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


class AudioChapterPayloadTests(TestCase):
    def setUp(self):
        self.book = Book.objects.create(
            author_name='Audio Author',
            slug='audio-payload-book',
            is_published=True,
            rights_status=Book.RightsStatus.LICENSED,
            pdf_generation_status='ready',
            audio_generation_status='ready',
        )
        BookTranslation.objects.create(
            book=self.book,
            title='Audio Payload',
            body='Body text for listening.',
        )

    def test_payload_empty_without_audio(self):
        self.assertEqual(self.book.get_audio_chapters_payload(), [])
        self.assertFalse(self.book.has_audio())

    def test_unique_book_order_constraint(self):
        from django.db import IntegrityError, transaction

        AudioChapter.objects.create(book=self.book, title='a', order=1)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AudioChapter.objects.create(book=self.book, title='b', order=1)
        AudioChapter.objects.create(book=self.book, title='c', order=2)
        self.assertEqual(AudioChapter.objects.filter(book=self.book).count(), 2)

    def test_payload_falls_back_to_legacy_audio_file(self):
        from django.core.files.base import ContentFile

        self.book.audio_file.save('legacy.mp3', ContentFile(b'\x00' * 64), save=True)
        payload = self.book.get_audio_chapters_payload()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]['title'], '1-qism')
        self.assertTrue(payload[0]['url'])
        self.assertTrue(self.book.has_audio())

    def test_payload_prefers_chapters_over_legacy(self):
        from django.core.files.base import ContentFile

        self.book.audio_file.save('legacy.mp3', ContentFile(b'\x00' * 64), save=True)
        ch2 = AudioChapter(book=self.book, title='2-bob', order=2)
        ch2.audio_file.save('ch2.mp3', ContentFile(b'\x01' * 64), save=True)
        ch1 = AudioChapter(book=self.book, title='1-bob', order=1)
        ch1.audio_file.save('ch1.mp3', ContentFile(b'\x02' * 64), save=True)
        ch3 = AudioChapter(book=self.book, title='', order=3)
        ch3.audio_file.save('ch3.mp3', ContentFile(b'\x03' * 64), save=True)

        payload = self.book.get_audio_chapters_payload()
        self.assertEqual(len(payload), 3)
        self.assertEqual([row['title'] for row in payload], ['1-bob', '2-bob', '3-qism'])
        self.assertTrue(self.book.has_audio())

    def test_reader_embeds_audio_chapters_json(self):
        from django.core.files.base import ContentFile
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(username='audio-reader', password='testpass123')
        Purchase.objects.create(
            user=user,
            book=self.book,
            status=Purchase.Status.PAID,
        )
        ch = AudioChapter(book=self.book, title='Intro', order=0)
        ch.audio_file.save('intro.mp3', ContentFile(b'\x00' * 64), save=True)

        self.client.login(username='audio-reader', password='testpass123')
        url = reverse('library:book-read', kwargs={'slug': self.book.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="audio-chapters-data"')
        content = response.content.decode()
        start = content.find('id="audio-chapters-data"')
        chunk = content[start : start + 800]
        json_start = chunk.find('>') + 1
        json_end = chunk.find('</script>')
        parsed = json.loads(chunk[json_start:json_end])
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]['title'], 'Intro')
        self.assertTrue(response.context['audio_url'])


class LibraryReaderTests(TestCase):
    def setUp(self):
        self.reader = User.objects.create_user(
            username='reader',
            password='testpass123',
        )
        self.book = Book.objects.create(
            author_name='Reader Author',
            slug='reader-test-book',
            is_published=True,
            rights_status=Book.RightsStatus.LICENSED,
            pdf_generation_status='ready',
            audio_generation_status='ready',
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
        Purchase.objects.create(
            user=self.reader,
            book=self.book,
            status=Purchase.Status.PAID,
        )

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

    def test_empty_body_detail_redirects_to_spa(self):
        empty_book = Book.objects.create(
            author_name='Empty Body',
            slug='empty-body-book',
            is_published=True,
            rights_status=Book.RightsStatus.LICENSED,
            pdf_generation_status='ready',
            audio_generation_status='ready',
        )
        BookTranslation.objects.create(
            book=empty_book,
            title='Empty Body Title',
            body='',
        )

        self.client.login(username='reader', password='testpass123')
        url = reverse('library:book-detail', kwargs={'slug': empty_book.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, spa_book_detail_url(empty_book.slug))

    def test_empty_body_read_redirects_to_spa_detail(self):
        empty_book = Book.objects.create(
            author_name='Empty Read',
            slug='empty-read-book',
            is_published=True,
            rights_status=Book.RightsStatus.LICENSED,
            pdf_generation_status='ready',
            audio_generation_status='ready',
        )
        BookTranslation.objects.create(
            book=empty_book,
            title='Empty Read Title',
            body='',
        )
        Purchase.objects.create(
            user=self.reader,
            book=empty_book,
            status=Purchase.Status.PAID,
        )

        self.client.login(username='reader', password='testpass123')
        url = reverse('library:book-read', kwargs={'slug': empty_book.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, spa_book_detail_url(empty_book.slug))
