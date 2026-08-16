"""Tests for byte-range streaming on gated audio media views."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from users.auth import get_tokens_for_user

from .models import AudioChapter, Book, BookTranslation, Purchase

User = get_user_model()

# 26 bytes — predictable slice boundaries for range assertions.
AUDIO_BYTES = b'ABCDEFGHIJKLMNOPQRSTUVWXYZ'


class AudioMediaRangeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='audiobuyer',
            password='Str0ng-Passw0rd!',
            email='audiobuyer@example.com',
        )
        self.other = User.objects.create_user(
            username='otheruser',
            password='Str0ng-Passw0rd!',
            email='other@example.com',
        )
        self.book = Book.objects.create(
            author_name='Range Author',
            category=Book.Category.NOVEL,
            slug='range-audio-book',
            is_published=True,
            rights_status=Book.RightsStatus.LICENSED,
            audio_file=SimpleUploadedFile(
                'chapter.mp3',
                AUDIO_BYTES,
                content_type='audio/mpeg',
            ),
        )
        BookTranslation.objects.create(
            book=self.book,
            language=BookTranslation.Language.UZ,
            title='Range kitob',
            body='Matn.',
        )
        Purchase.objects.create(
            user=self.user,
            book=self.book,
            status=Purchase.Status.PAID,
        )
        self.chapter = AudioChapter.objects.create(
            book=self.book,
            title='1-qism',
            order=0,
            audio_file=SimpleUploadedFile(
                'part1.mp3',
                AUDIO_BYTES,
                content_type='audio/mpeg',
            ),
        )

    def _audio_url(self):
        return reverse('library:book-media-audio', kwargs={'slug': self.book.slug})

    def _chapter_url(self):
        return reverse(
            'library:book-media-chapter-audio',
            kwargs={'slug': self.book.slug, 'chapter_id': self.chapter.pk},
        )

    def _login(self, user=None):
        user = user or self.user
        tokens = get_tokens_for_user(user)
        self.client.cookies[settings.JWT_ACCESS_COOKIE_NAME] = tokens['access']
        self.client.cookies[settings.JWT_REFRESH_COOKIE_NAME] = tokens['refresh']

    def _body(self, response):
        if hasattr(response, 'streaming_content'):
            return b''.join(response.streaming_content)
        return response.content

    def test_full_response_without_range_header(self):
        self._login()
        response = self.client.get(self._audio_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Accept-Ranges'], 'bytes')
        self.assertEqual(self._body(response), AUDIO_BYTES)
        self.assertNotIn('Content-Range', response)

    def test_partial_content_returns_expected_bytes(self):
        self._login()
        response = self.client.get(self._audio_url(), HTTP_RANGE='bytes=0-9')
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response['Content-Range'], f'bytes 0-9/{len(AUDIO_BYTES)}')
        self.assertEqual(response['Content-Length'], '10')
        self.assertEqual(response['Accept-Ranges'], 'bytes')
        self.assertEqual(self._body(response), AUDIO_BYTES[:10])

    def test_chapter_audio_partial_content(self):
        self._login()
        response = self.client.get(self._chapter_url(), HTTP_RANGE='bytes=10-15')
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response['Content-Range'], f'bytes 10-15/{len(AUDIO_BYTES)}')
        self.assertEqual(self._body(response), AUDIO_BYTES[10:16])

    def test_out_of_bounds_range_returns_416(self):
        self._login()
        response = self.client.get(
            self._audio_url(),
            HTTP_RANGE=f'bytes={len(AUDIO_BYTES)}-{len(AUDIO_BYTES) + 99}',
        )
        self.assertEqual(response.status_code, 416)
        self.assertEqual(response['Content-Range'], f'bytes */{len(AUDIO_BYTES)}')
        self.assertEqual(response['Accept-Ranges'], 'bytes')

    def test_unauthenticated_range_request_not_partial(self):
        response = self.client.get(
            self._audio_url(),
            HTTP_RANGE='bytes=0-9',
            HTTP_ACCEPT='application/json',
        )
        self.assertEqual(response.status_code, 401)
        self.assertNotEqual(response.status_code, 206)

    def test_unentitled_range_request_not_partial(self):
        self._login(self.other)
        response = self.client.get(
            self._audio_url(),
            HTTP_RANGE='bytes=0-9',
            HTTP_ACCEPT='application/json',
        )
        self.assertEqual(response.status_code, 403)
        self.assertNotEqual(response.status_code, 206)

    def test_malformed_range_falls_back_to_full_200(self):
        self._login()
        response = self.client.get(self._audio_url(), HTTP_RANGE='bytes=abc-def')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Accept-Ranges'], 'bytes')
        self.assertEqual(self._body(response), AUDIO_BYTES)

    def test_multi_range_falls_back_to_full_200(self):
        self._login()
        response = self.client.get(
            self._audio_url(),
            HTTP_RANGE='bytes=0-9,10-19',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._body(response), AUDIO_BYTES)


PDF_BYTES = b'%PDF-1.4 public-domain-range-fixture'


class PublicDomainPdfRangeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='pdfrange',
            password='Str0ng-Passw0rd!',
            email='pdfrange@example.com',
        )
        self.book = Book.objects.create(
            author_name='Public Range',
            category=Book.Category.HISTORY,
            slug='public-pdf-range',
            is_published=True,
            rights_status=Book.RightsStatus.PUBLIC_DOMAIN,
            pdf_file=SimpleUploadedFile(
                'public.pdf',
                PDF_BYTES,
                content_type='application/pdf',
            ),
        )
        BookTranslation.objects.create(
            book=self.book,
            language=BookTranslation.Language.UZ,
            title='Public range',
            body='Matn.',
        )

    def _login(self):
        tokens = get_tokens_for_user(self.user)
        self.client.cookies[settings.JWT_ACCESS_COOKIE_NAME] = tokens['access']
        self.client.cookies[settings.JWT_REFRESH_COOKIE_NAME] = tokens['refresh']

    def _pdf_url(self):
        return reverse('library:book-media-pdf', kwargs={'slug': self.book.slug})

    def _body(self, response):
        if hasattr(response, 'streaming_content'):
            return b''.join(response.streaming_content)
        return response.content

    def test_public_domain_pdf_range(self):
        self._login()
        response = self.client.get(self._pdf_url(), HTTP_RANGE='bytes=0-10')
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response['Accept-Ranges'], 'bytes')
        self.assertEqual(response['Content-Range'], f'bytes 0-10/{len(PDF_BYTES)}')
        self.assertEqual(self._body(response), PDF_BYTES[:11])

    def test_public_domain_pdf_full_body_unchanged(self):
        self._login()
        response = self.client.get(self._pdf_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._body(response), PDF_BYTES)

