"""Unit tests for generation queue health, rights gating, and mocked PDF/TTS."""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from library.generation_health import generation_health_payload
from library.generation_utils import GENERATION_READY
from library.jobs import (
    GenerationEnqueueError,
    claim_next_job,
    enqueue_generation_job,
    run_job,
)
from library.models import Book, BookTranslation, GenerationJob

User = get_user_model()


class GenerationHealthTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='staffer', password='Str0ng-Passw0rd!', is_staff=True
        )
        self.user = User.objects.create_user(
            username='reader', password='Str0ng-Passw0rd!'
        )
        self.book = Book.objects.create(
            author_name='A',
            slug='health-book',
            rights_status=Book.RightsStatus.LICENSED,
            pdf_generation_status='ready',
            audio_generation_status='ready',
        )

    def test_stale_queued_marks_worker_likely_down(self):
        job = GenerationJob.objects.create(
            book=self.book,
            job_type=GenerationJob.JobType.ALL,
            status=GenerationJob.Status.QUEUED,
        )
        GenerationJob.objects.filter(pk=job.pk).update(
            created_at=timezone.now() - timedelta(minutes=10)
        )
        payload = generation_health_payload()
        self.assertTrue(payload['worker_likely_down'])
        self.assertGreaterEqual(payload['stale_queued'], 1)

    def test_health_endpoint_staff_only(self):
        url = reverse('generation-health')
        self.assertIn(
            self.client.get(url).status_code, (302, 401)
        )
        self.client.login(username='reader', password='Str0ng-Passw0rd!')
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.logout()
        self.client.login(username='staffer', password='Str0ng-Passw0rd!')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('queued', response.json())


class GenerationRightsAndQuotaTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='admin2', password='Str0ng-Passw0rd!', is_staff=True
        )
        self.book = Book.objects.create(
            author_name='B',
            slug='rights-book',
            rights_status=Book.RightsStatus.UNSET,
        )
        BookTranslation.objects.create(
            book=self.book,
            language=BookTranslation.Language.UZ,
            title='Huquq',
            body='Matn.',
        )

    def test_enqueue_blocked_without_rights(self):
        with self.assertRaises(GenerationEnqueueError):
            enqueue_generation_job(self.book.pk, force=False)

    def test_enqueue_allowed_when_licensed(self):
        self.book.rights_status = Book.RightsStatus.LICENSED
        self.book.save(update_fields=['rights_status'])
        job = enqueue_generation_job(self.book.pk)
        self.assertIsNotNone(job)
        self.assertEqual(job.status, GenerationJob.Status.QUEUED)

    @override_settings(GENERATION_REGENERATE_DAILY_LIMIT=1)
    def test_regenerate_daily_cap(self):
        self.book.rights_status = Book.RightsStatus.LICENSED
        self.book.save(update_fields=['rights_status'])
        enqueue_generation_job(self.book.pk, force=True, user=self.staff)
        other = Book.objects.create(
            author_name='C',
            slug='rights-book-2',
            rights_status=Book.RightsStatus.LICENSED,
        )
        with self.assertRaises(GenerationEnqueueError):
            enqueue_generation_job(other.pk, force=True, user=self.staff)


class GenerationJobRunTests(TestCase):
    def setUp(self):
        self.book = Book.objects.create(
            author_name='D',
            slug='gen-run-book',
            rights_status=Book.RightsStatus.LICENSED,
        )
        BookTranslation.objects.create(
            book=self.book,
            language=BookTranslation.Language.UZ,
            title='Sinov',
            body='Birinchi.\n\nIkkinchi.',
        )

    @patch('library.jobs.ensure_book_audio', return_value=GENERATION_READY)
    @patch('library.jobs.ensure_book_pdf', return_value=GENERATION_READY)
    def test_run_job_marks_done(self, _pdf, _audio):
        job = enqueue_generation_job(self.book.pk)
        claimed = claim_next_job()
        self.assertEqual(claimed.pk, job.pk)
        run_job(claimed)
        claimed.refresh_from_db()
        self.assertEqual(claimed.status, GenerationJob.Status.DONE)

    @override_settings(GENERATION_MAX_RUNNING=0)
    def test_concurrency_cap_blocks_claim(self):
        enqueue_generation_job(self.book.pk)
        self.assertIsNone(claim_next_job())


class GenerationJobUniquenessTests(TestCase):
    def setUp(self):
        self.book = Book.objects.create(
            author_name='E',
            slug='uniq-job-book',
            rights_status=Book.RightsStatus.LICENSED,
        )

    def test_constraint_rejects_second_active_job(self):
        from django.db import IntegrityError, transaction

        GenerationJob.objects.create(
            book=self.book,
            job_type=GenerationJob.JobType.ALL,
            status=GenerationJob.Status.QUEUED,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                GenerationJob.objects.create(
                    book=self.book,
                    job_type=GenerationJob.JobType.ALL,
                    status=GenerationJob.Status.QUEUED,
                )

    def test_enqueue_returns_same_active_job(self):
        first = enqueue_generation_job(self.book.pk)
        second = enqueue_generation_job(self.book.pk)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(
            GenerationJob.objects.filter(
                book=self.book,
                status__in=[GenerationJob.Status.QUEUED, GenerationJob.Status.RUNNING],
            ).count(),
            1,
        )


class GenerationJobConcurrentEnqueueTests(TransactionTestCase):
    """True concurrent enqueue against the partial unique index."""

    def test_two_threads_create_one_active_job(self):
        import threading

        from django.db import connection

        if connection.vendor == 'sqlite':
            self.skipTest(
                'SQLite serializes writers (database is locked); '
                'constraint coverage is in GenerationJobUniquenessTests. '
                'Run this race on Postgres.'
            )

        book = Book.objects.create(
            author_name='F',
            slug='race-job-book',
            rights_status=Book.RightsStatus.LICENSED,
        )
        results = []
        barrier = threading.Barrier(2)

        def worker():
            barrier.wait(timeout=5)
            job = enqueue_generation_job(book.pk)
            results.append(job.pk if job else None)

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        self.assertEqual(len(results), 2)
        self.assertTrue(all(results))
        self.assertEqual(results[0], results[1])
        self.assertEqual(
            GenerationJob.objects.filter(
                book=book,
                status__in=[GenerationJob.Status.QUEUED, GenerationJob.Status.RUNNING],
            ).count(),
            1,
        )
