"""Purchase entitlement gating for PDF/audio media and immersive reader."""

from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from pypdf import PdfReader, PdfWriter

from .models import Book, BookTranslation, Purchase
from .pdf_test_utils import sample_pdf_bytes
from .pdf_watermark import (
    INFO_KEY,
    WATERMARK_PREFIX,
    license_fingerprint,
    license_identifier,
    overlay_label,
    stamp_pdf_bytes,
)
from .test_auth_helpers import authenticate_jwt

User = get_user_model()


class PurchaseMediaAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='buyer',
            password='testpass123',
            email='buyer@example.com',
        )
        self.licensed = Book.objects.create(
            author_name='Licensed Author',
            category=Book.Category.NOVEL,
            slug='licensed-paid-book',
            is_published=True,
            rights_status=Book.RightsStatus.LICENSED,
            pdf_generation_status='ready',
            audio_generation_status='ready',
            pdf_file=SimpleUploadedFile(
                'licensed.pdf',
                sample_pdf_bytes(title='Licensed sample'),
                content_type='application/pdf',
            ),
        )
        BookTranslation.objects.create(
            book=self.licensed,
            language=BookTranslation.Language.UZ,
            title='Pullik kitob',
            summary='Qisqa.',
            body='Pullik matn.',
        )
        self.public = Book.objects.create(
            author_name='Public Author',
            category=Book.Category.HISTORY,
            slug='public-domain-book',
            is_published=True,
            rights_status=Book.RightsStatus.PUBLIC_DOMAIN,
            pdf_generation_status='ready',
            audio_generation_status='ready',
            pdf_file=SimpleUploadedFile(
                'public.pdf',
                b'%PDF-1.4 public',
                content_type='application/pdf',
            ),
        )
        BookTranslation.objects.create(
            book=self.public,
            language=BookTranslation.Language.UZ,
            title='Bepul kitob',
            summary='Qisqa.',
            body='Bepul matn.',
        )

    def _pdf_url(self, book):
        return reverse('library:book-media-pdf', kwargs={'slug': book.slug})

    def _read_url(self, book):
        return reverse('library:book-read', kwargs={'slug': book.slug})

    def test_licensed_without_purchase_blocked(self):
        authenticate_jwt(self.client, self.user)
        response = self.client.get(
            self._pdf_url(self.licensed),
            HTTP_ACCEPT='application/json',
        )
        self.assertEqual(response.status_code, 403)

    def test_pending_purchase_still_blocked(self):
        Purchase.objects.create(
            user=self.user,
            book=self.licensed,
            status=Purchase.Status.PENDING,
        )
        authenticate_jwt(self.client, self.user)
        response = self.client.get(
            self._pdf_url(self.licensed),
            HTTP_ACCEPT='application/json',
        )
        self.assertEqual(response.status_code, 403)

    def test_paid_purchase_allows_media(self):
        Purchase.objects.create(
            user=self.user,
            book=self.licensed,
            status=Purchase.Status.PAID,
            paid_at=timezone.now(),
        )
        authenticate_jwt(self.client, self.user)
        response = self.client.get(self._pdf_url(self.licensed))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def _pdf_body(self, response):
        if getattr(response, 'streaming', False):
            return b''.join(response.streaming_content)
        return response.content

    def test_licensed_pdf_embeds_purchase_identifier(self):
        Purchase.objects.create(
            user=self.user,
            book=self.licensed,
            status=Purchase.Status.PAID,
            paid_at=timezone.now(),
        )
        authenticate_jwt(self.client, self.user)
        response = self.client.get(self._pdf_url(self.licensed))
        self.assertEqual(response.status_code, 200)
        body = self._pdf_body(response)
        purchase = Purchase.objects.get(user=self.user, book=self.licensed)
        ident = license_identifier(user=self.user, purchase=purchase)
        reader = PdfReader(BytesIO(body))
        extracted = '\n'.join(page.extract_text() or '' for page in reader.pages)
        self.assertIn(WATERMARK_PREFIX, extracted)
        self.assertIn(ident, extracted)
        self.assertEqual(str(reader.metadata[INFO_KEY]), ident)

    def test_two_purchases_embed_different_identifiers(self):
        other = User.objects.create_user(
            username='buyer2',
            password='testpass123',
            email='buyer2@example.com',
        )
        p1 = Purchase.objects.create(
            user=self.user,
            book=self.licensed,
            status=Purchase.Status.PAID,
            paid_at=timezone.now(),
        )
        p2 = Purchase.objects.create(
            user=other,
            book=self.licensed,
            status=Purchase.Status.PAID,
            paid_at=timezone.now(),
        )
        authenticate_jwt(self.client, self.user)
        body1 = self._pdf_body(self.client.get(self._pdf_url(self.licensed)))
        self.client.cookies.clear()
        authenticate_jwt(self.client, other)
        body2 = self._pdf_body(self.client.get(self._pdf_url(self.licensed)))
        id1 = license_identifier(user=self.user, purchase=p1)
        id2 = license_identifier(user=other, purchase=p2)
        self.assertNotEqual(id1, id2)
        text1 = '\n'.join(
            page.extract_text() or '' for page in PdfReader(BytesIO(body1)).pages
        )
        text2 = '\n'.join(
            page.extract_text() or '' for page in PdfReader(BytesIO(body2)).pages
        )
        self.assertIn(id1, text1)
        self.assertIn(id2, text2)
        self.assertNotIn(id2, text1)
        self.assertNotIn(id1, text2)
        meta1 = PdfReader(BytesIO(body1)).metadata
        meta2 = PdfReader(BytesIO(body2)).metadata
        self.assertEqual(str(meta1[INFO_KEY]), id1)
        self.assertEqual(str(meta2[INFO_KEY]), id2)

    def test_licensed_pdf_supports_http_range_from_stamp_cache(self):
        Purchase.objects.create(
            user=self.user,
            book=self.licensed,
            status=Purchase.Status.PAID,
            paid_at=timezone.now(),
        )
        authenticate_jwt(self.client, self.user)
        full = self.client.get(self._pdf_url(self.licensed))
        self.assertEqual(full.status_code, 200)
        full_body = self._pdf_body(full)
        ranged = self.client.get(
            self._pdf_url(self.licensed),
            HTTP_RANGE='bytes=0-10',
        )
        self.assertEqual(ranged.status_code, 206)
        self.assertEqual(ranged['Accept-Ranges'], 'bytes')
        self.assertEqual(self._pdf_body(ranged), full_body[:11])
        with patch('library.media_views.stamp_pdf_bytes') as mocked:
            again = self.client.get(self._pdf_url(self.licensed))
            self.assertEqual(again.status_code, 200)
            mocked.assert_not_called()

    def test_stamp_real_pdf_remains_parseable_with_startxref(self):
        payload = sample_pdf_bytes(title='Parser regression', pages=1)
        ident = 'buyer@example.com|purchase:1'
        stamped = stamp_pdf_bytes(payload, ident, stamped_at_iso='2026-08-16T12:00Z')
        self.assertIn(b'startxref', stamped)
        self.assertTrue(stamped.rstrip().endswith(b'%%EOF') or b'%%EOF' in stamped[-32:])
        reader = PdfReader(BytesIO(stamped))
        self.assertGreaterEqual(len(reader.pages), 1)
        extracted = reader.pages[0].extract_text() or ''
        self.assertIn(overlay_label(ident, '2026-08-16T12:00Z'), extracted)
        self.assertEqual(str(reader.metadata[INFO_KEY]), ident)
        catalog = reader.trailer['/Root']
        self.assertEqual(str(catalog['/LibroUZ']['/LicenseId']), ident)
        self.assertEqual(
            str(catalog['/LibroUZ']['/LicenseHash']),
            license_fingerprint(ident),
        )
        xmp = reader.xmp_metadata
        xmp_text = xmp.stream.get_data().decode('utf-8')
        self.assertIn(ident, xmp_text)
        self.assertIn(license_fingerprint(ident), xmp_text)

    def test_stamp_preserves_embedded_file_attachment(self):
        source = PdfWriter()
        source.append(PdfReader(BytesIO(sample_pdf_bytes(pages=1))))
        source.add_attachment('license-note.txt', b'keep-me')
        buf = BytesIO()
        source.write(buf)
        stamped = stamp_pdf_bytes(
            buf.getvalue(),
            'attach@example.com|purchase:7',
            stamped_at_iso='2026-08-16T12:00Z',
        )
        attached = PdfReader(BytesIO(stamped)).attachments
        self.assertIn('license-note.txt', attached)
        blobs = attached['license-note.txt']
        payload = blobs if isinstance(blobs, (bytes, bytearray)) else blobs[0]
        self.assertEqual(payload, b'keep-me')

    def test_visible_overlay_is_page_content_not_trailing_comment(self):
        payload = sample_pdf_bytes(title='Overlay check', pages=2)
        ident = 'overlay@example.com|purchase:99'
        stamped = stamp_pdf_bytes(payload, ident, stamped_at_iso='2026-08-16T12:00Z')
        self.assertFalse(stamped.startswith(payload))
        reader = PdfReader(BytesIO(stamped))
        self.assertEqual(len(reader.pages), 2)
        for page in reader.pages:
            text = page.extract_text() or ''
            self.assertIn(WATERMARK_PREFIX, text)
            self.assertIn(ident, text)

    def test_stamp_not_called_without_purchase_or_when_unpublished(self):
        authenticate_jwt(self.client, self.user)
        with patch('library.media_views.stamp_pdf_bytes') as mocked:
            blocked = self.client.get(
                self._pdf_url(self.licensed),
                HTTP_ACCEPT='application/json',
            )
            self.assertEqual(blocked.status_code, 403)
            mocked.assert_not_called()

        Purchase.objects.create(
            user=self.user,
            book=self.licensed,
            status=Purchase.Status.PAID,
            paid_at=timezone.now(),
        )
        self.licensed.is_published = False
        self.licensed.save(update_fields=['is_published'])
        with patch('library.media_views.stamp_pdf_bytes') as mocked:
            missing = self.client.get(self._pdf_url(self.licensed))
            self.assertEqual(missing.status_code, 404)
            mocked.assert_not_called()

    def test_public_domain_pdf_is_not_watermarked(self):
        authenticate_jwt(self.client, self.user)
        with self.public.pdf_file.open('rb') as handle:
            original = handle.read()
        response = self.client.get(self._pdf_url(self.public))
        self.assertEqual(response.status_code, 200)
        body = self._pdf_body(response)
        self.assertEqual(body, original)
        self.assertNotIn(WATERMARK_PREFIX.encode('utf-8'), body)

    def test_public_domain_allows_without_purchase(self):
        authenticate_jwt(self.client, self.user)
        response = self.client.get(self._pdf_url(self.public))
        self.assertEqual(response.status_code, 200)

    def test_reader_requires_paid_for_licensed(self):
        """HTML reader removed — /read/ redirects to SPA; entitlement is API-gated."""
        from .spa_urls import spa_book_read_url

        authenticate_jwt(self.client, self.user)
        blocked = self.client.get(self._read_url(self.licensed))
        self.assertEqual(blocked.status_code, 302)
        self.assertEqual(blocked.url, spa_book_read_url(self.licensed.slug))

        # Without purchase, manifest is 403.
        locked = self.client.get(
            reverse('library_api:reader-manifest', kwargs={'slug': self.licensed.slug}),
        )
        self.assertEqual(locked.status_code, 403)

        Purchase.objects.create(
            user=self.user,
            book=self.licensed,
            status=Purchase.Status.PAID,
            paid_at=timezone.now(),
        )
        allowed = self.client.get(self._read_url(self.licensed))
        self.assertEqual(allowed.status_code, 302)
        self.assertEqual(allowed.url, spa_book_read_url(self.licensed.slug))

        manifest = self.client.get(
            reverse('library_api:reader-manifest', kwargs={'slug': self.licensed.slug}),
        )
        self.assertEqual(manifest.status_code, 200)
        self.assertIn('body', manifest.json())


class PurchaseAccessAPIDetailTests(TestCase):
    """Detail JSON must not advertise media URLs when the user lacks access."""

    def setUp(self):
        from django.conf import settings

        from users.auth import get_tokens_for_user

        self.settings = settings
        self.get_tokens_for_user = get_tokens_for_user
        self.user = User.objects.create_user(
            username='apibuyer',
            password='testpass123',
            email='apibuyer@example.com',
        )
        self.licensed = Book.objects.create(
            author_name='Licensed Author',
            category=Book.Category.NOVEL,
            slug='api-licensed-book',
            is_published=True,
            rights_status=Book.RightsStatus.LICENSED,
            pdf_generation_status='ready',
            audio_generation_status='ready',
            pdf_file=SimpleUploadedFile(
                'licensed.pdf',
                b'%PDF-1.4 licensed',
                content_type='application/pdf',
            ),
        )
        BookTranslation.objects.create(
            book=self.licensed,
            language=BookTranslation.Language.UZ,
            title='API pullik',
            summary='Qisqa.',
            body='Matn.',
        )
        self.public = Book.objects.create(
            author_name='Fyodor Dostoyevskiy',
            category=Book.Category.NOVEL,
            slug='api-public-book',
            is_published=True,
            rights_status=Book.RightsStatus.PUBLIC_DOMAIN,
            pdf_generation_status='ready',
            audio_generation_status='ready',
            pdf_file=SimpleUploadedFile(
                'public.pdf',
                b'%PDF-1.4 public',
                content_type='application/pdf',
            ),
        )
        BookTranslation.objects.create(
            book=self.public,
            language=BookTranslation.Language.UZ,
            title='Jinoyat va jazo',
            summary='Qisqa.',
            body='Bepul matn.',
        )

    def _login(self):
        tokens = self.get_tokens_for_user(self.user)
        self.client.cookies[self.settings.JWT_ACCESS_COOKIE_NAME] = tokens['access']

    def test_detail_hides_urls_without_purchase(self):
        self._login()
        url = reverse('library_api:book-detail', kwargs={'slug': self.licensed.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['has_access'])
        self.assertFalse(data['can_read'])
        self.assertEqual(data['pdf_url'], '')
        self.assertEqual(data['audio_url'], '')
        self.assertTrue(data['has_pdf'])

    def test_detail_public_domain_includes_urls(self):
        self._login()
        url = reverse('library_api:book-detail', kwargs={'slug': self.public.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['has_access'])
        self.assertTrue(data['can_read'])
        self.assertTrue(data['pdf_url'].startswith('/library/media/'))

    def test_detail_paid_purchase_includes_urls(self):
        Purchase.objects.create(
            user=self.user,
            book=self.licensed,
            status=Purchase.Status.PAID,
            paid_at=timezone.now(),
        )
        self._login()
        url = reverse('library_api:book-detail', kwargs={'slug': self.licensed.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['has_access'])
        self.assertTrue(data['pdf_url'].startswith('/library/media/'))


class BookDetailActionRegressionTests(TestCase):
    """Regression: public_domain actions work; gated books return clear 403/locked API."""

    def setUp(self):
        from django.conf import settings

        from users.auth import get_tokens_for_user

        self.settings = settings
        self.get_tokens_for_user = get_tokens_for_user
        self.user = User.objects.create_user(
            username='regression',
            password='testpass123',
            email='regression@example.com',
        )
        media_pdf = SimpleUploadedFile(
            'book.pdf',
            b'%PDF-1.4 test',
            content_type='application/pdf',
        )
        media_audio = SimpleUploadedFile(
            'book.mp3',
            b'ID3fakeaudio',
            content_type='audio/mpeg',
        )
        self.licensed = Book.objects.create(
            author_name='Licensed Author',
            category=Book.Category.NOVEL,
            slug='regression-licensed',
            is_published=True,
            rights_status=Book.RightsStatus.LICENSED,
            pdf_generation_status='ready',
            audio_generation_status='ready',
            pdf_file=media_pdf,
            audio_file=media_audio,
        )
        BookTranslation.objects.create(
            book=self.licensed,
            language=BookTranslation.Language.UZ,
            title='Pullik kitob',
            summary='Qisqa.',
            body='Pullik matn.',
        )
        self.public = Book.objects.create(
            author_name='Public Author',
            category=Book.Category.HISTORY,
            slug='regression-public',
            is_published=True,
            rights_status=Book.RightsStatus.PUBLIC_DOMAIN,
            pdf_generation_status='ready',
            audio_generation_status='ready',
            pdf_file=SimpleUploadedFile(
                'public.pdf',
                b'%PDF-1.4 public',
                content_type='application/pdf',
            ),
            audio_file=SimpleUploadedFile(
                'public.mp3',
                b'ID3publicaudio',
                content_type='audio/mpeg',
            ),
        )
        BookTranslation.objects.create(
            book=self.public,
            language=BookTranslation.Language.UZ,
            title='Bepul kitob',
            summary='Qisqa.',
            body='Bepul matn.',
        )

    def _login(self):
        tokens = self.get_tokens_for_user(self.user)
        self.client.cookies[self.settings.JWT_ACCESS_COOKIE_NAME] = tokens['access']

    def _pdf_url(self, book):
        return reverse('library:book-media-pdf', kwargs={'slug': book.slug})

    def _audio_url(self, book):
        return reverse('library:book-media-audio', kwargs={'slug': book.slug})

    def _read_url(self, book):
        return reverse('library:book-read', kwargs={'slug': book.slug})

    def _api_detail_url(self, book):
        return reverse('library_api:book-detail', kwargs={'slug': book.slug})

    def test_public_domain_read_pdf_audio_and_api(self):
        from .spa_urls import spa_book_read_url

        self._login()
        read = self.client.get(self._read_url(self.public), HTTP_ACCEPT='application/json')
        self.assertEqual(read.status_code, 302)
        self.assertEqual(read.url, spa_book_read_url(self.public.slug))

        pdf = self.client.get(self._pdf_url(self.public))
        self.assertEqual(pdf.status_code, 200)

        audio = self.client.get(self._audio_url(self.public))
        self.assertEqual(audio.status_code, 200)

        detail = self.client.get(self._api_detail_url(self.public))
        self.assertEqual(detail.status_code, 200)
        data = detail.json()
        self.assertTrue(data['has_access'])
        self.assertTrue(data['can_read'])
        self.assertTrue(data['has_pdf'])
        self.assertTrue(data['has_audio'])
        self.assertTrue(data['pdf_url'].startswith('/library/media/'))
        self.assertTrue(data['audio_url'].startswith('/library/media/'))

    def test_gated_book_returns_403_and_locked_api(self):
        from .spa_urls import spa_book_read_url

        self._login()
        read = self.client.get(
            self._read_url(self.licensed),
            HTTP_ACCEPT='application/json',
        )
        self.assertEqual(read.status_code, 302)
        self.assertEqual(read.url, spa_book_read_url(self.licensed.slug))

        pdf = self.client.get(
            self._pdf_url(self.licensed),
            HTTP_ACCEPT='application/json',
        )
        self.assertEqual(pdf.status_code, 403)
        self.assertIn('Purchase required', pdf.json()['detail'])

        audio = self.client.get(
            self._audio_url(self.licensed),
            HTTP_ACCEPT='application/json',
        )
        self.assertEqual(audio.status_code, 403)
        self.assertIn('Purchase required', audio.json()['detail'])

        detail = self.client.get(self._api_detail_url(self.licensed))
        self.assertEqual(detail.status_code, 200)
        data = detail.json()
        self.assertFalse(data['has_access'])
        self.assertFalse(data['can_read'])
        self.assertEqual(data['pdf_url'], '')
        self.assertEqual(data['audio_url'], '')
        self.assertTrue(data['has_pdf'])
        self.assertTrue(data['has_audio'])
