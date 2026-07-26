"""Purchase entitlement gating for PDF/audio media and immersive reader."""

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Book, BookTranslation, Purchase

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
                b'%PDF-1.4 licensed',
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
        self.client.login(username='buyer', password='testpass123')
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
        self.client.login(username='buyer', password='testpass123')
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
        self.client.login(username='buyer', password='testpass123')
        response = self.client.get(self._pdf_url(self.licensed))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_public_domain_allows_without_purchase(self):
        self.client.login(username='buyer', password='testpass123')
        response = self.client.get(self._pdf_url(self.public))
        self.assertEqual(response.status_code, 200)

    def test_reader_requires_paid_for_licensed(self):
        self.client.login(username='buyer', password='testpass123')
        blocked = self.client.get(
            self._read_url(self.licensed),
            HTTP_ACCEPT='application/json',
        )
        self.assertEqual(blocked.status_code, 403)

        Purchase.objects.create(
            user=self.user,
            book=self.licensed,
            status=Purchase.Status.PAID,
            paid_at=timezone.now(),
        )
        allowed = self.client.get(self._read_url(self.licensed))
        self.assertEqual(allowed.status_code, 200)
        self.assertContains(allowed, 'Pullik matn')
