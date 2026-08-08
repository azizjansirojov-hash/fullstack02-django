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
from library.test_auth_helpers import authenticate_jwt

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

    def test_stale_running_marks_worker_likely_down(self):
        """A RUNNING job whose lock_at is older than STALE_RUNNING_SECONDS should
        flag worker_likely_down even when there are no stale queued jobs."""
        from library.jobs import STALE_RUNNING_SECONDS

        job = GenerationJob.objects.create(
            book=self.book,
            job_type=GenerationJob.JobType.PDF,
            status=GenerationJob.Status.RUNNING,
            locked_by='dead-worker-abc',
        )
        # Backdate locked_at beyond the stale window.
        stale_ago = timezone.now() - timedelta(seconds=STALE_RUNNING_SECONDS + 60)
        GenerationJob.objects.filter(pk=job.pk).update(locked_at=stale_ago)

        payload = generation_health_payload()
        self.assertTrue(payload['worker_likely_down'])
        self.assertGreaterEqual(payload['stale_running'], 1)
        self.assertEqual(payload['status'], 'degraded')

    def test_fresh_running_does_not_flag_degraded(self):
        """A recently-locked RUNNING job should not trigger worker_likely_down."""
        GenerationJob.objects.create(
            book=self.book,
            job_type=GenerationJob.JobType.AUDIO,
            status=GenerationJob.Status.RUNNING,
            locked_by='live-worker-xyz',
            locked_at=timezone.now(),
        )
        payload = generation_health_payload()
        self.assertFalse(payload['worker_likely_down'])
        self.assertEqual(payload['stale_running'], 0)
        self.assertEqual(payload['status'], 'ok')

    def test_health_endpoint_staff_only(self):
        url = reverse('generation-health')
        self.assertIn(
            self.client.get(url).status_code, (302, 401)
        )
        authenticate_jwt(self.client, self.user)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.logout()
        authenticate_jwt(self.client, self.staff)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('queued', data)
        self.assertIn('stale_running', data)
        self.assertIn('stale_running_after_seconds', data)

    def test_failed_recent_surfaced_in_health_payload(self):
        job = GenerationJob.objects.create(
            book=self.book,
            job_type=GenerationJob.JobType.AUDIO,
            status=GenerationJob.Status.FAILED,
            error_message='edge-tts timed out',
        )
        payload = generation_health_payload()
        self.assertGreaterEqual(payload['failed_recent_24h'], 1)
        self.assertIsNotNone(payload['last_failed'])
        self.assertEqual(payload['last_failed']['job_id'], job.pk)
        self.assertIn('edge-tts', payload['last_failed']['error_message'])


class TtsProviderConfigTests(TestCase):
    @override_settings(TTS_PROVIDER='azure-fantasy')
    def test_unknown_provider_raises_not_implemented(self):
        from library.tts_providers import get_tts_provider

        with self.assertRaises(NotImplementedError) as ctx:
            get_tts_provider()
        msg = str(ctx.exception)
        self.assertIn('tts_providers', msg)
        self.assertIn('azure-fantasy', msg)


class EdgeTtsRetryTests(TestCase):
    @patch('library.tts_providers.edge.time.sleep', return_value=None)
    @patch('library.tts_providers.edge._run_async')
    def test_synthesize_retries_then_succeeds(self, mock_run, _sleep):
        from library.tts_providers.edge import EdgeTTSProvider

        mock_run.side_effect = [
            RuntimeError('edge-tts timed out after 120 s'),
            b'ID3fake-mp3',
        ]
        out = EdgeTTSProvider().synthesize('Salom.', voice='uz-UZ-MadinaNeural')
        self.assertEqual(out, b'ID3fake-mp3')
        self.assertEqual(mock_run.call_count, 2)

    @patch('library.tts_providers.edge.time.sleep', return_value=None)
    @patch('library.tts_providers.edge._run_async')
    def test_synthesize_exhausts_retries(self, mock_run, _sleep):
        from library.tts_providers.edge import EdgeTTSProvider

        mock_run.side_effect = RuntimeError('edge-tts timed out after 120 s')
        with self.assertRaises(RuntimeError):
            EdgeTTSProvider().synthesize('Salom.', voice='uz-UZ-MadinaNeural')
        self.assertEqual(mock_run.call_count, 3)


class TtsJobFailureStatusTests(TestCase):
    def setUp(self):
        self.book = Book.objects.create(
            author_name='TTS',
            slug='tts-fail-book',
            rights_status=Book.RightsStatus.LICENSED,
            audio_generation_status='pending',
        )
        BookTranslation.objects.create(
            book=self.book,
            language=BookTranslation.Language.UZ,
            title='TTS',
            body='Birinchi jumla.',
        )

    @patch('library.jobs.ensure_book_audio', return_value='failed')
    def test_retry_keeps_book_generating_until_terminal(self, _audio):
        from library.generation_utils import GENERATION_FAILED, GENERATION_GENERATING

        self.book.audio_generation_status = GENERATION_GENERATING
        self.book.save(update_fields=['audio_generation_status'])

        job = GenerationJob.objects.create(
            book=self.book,
            job_type=GenerationJob.JobType.AUDIO,
            status=GenerationJob.Status.QUEUED,
            max_attempts=3,
            attempts=0,
        )
        # First claim: attempts=1 < max → requeue; book stays generating.
        claimed = claim_next_job()
        self.assertEqual(claimed.pk, job.pk)
        run_job(claimed)
        claimed.refresh_from_db()
        self.book.refresh_from_db()
        self.assertEqual(claimed.status, GenerationJob.Status.QUEUED)
        self.assertEqual(self.book.audio_generation_status, GENERATION_GENERATING)

        # Burn remaining attempts to terminal failure.
        for _ in range(2):
            claimed = claim_next_job()
            self.assertIsNotNone(claimed)
            run_job(claimed)

        claimed.refresh_from_db()
        self.book.refresh_from_db()
        self.assertEqual(claimed.status, GenerationJob.Status.FAILED)
        self.assertEqual(self.book.audio_generation_status, GENERATION_FAILED)
        payload = generation_health_payload()
        self.assertGreaterEqual(payload['failed_recent_24h'], 1)
        self.assertEqual(payload['last_failed']['job_id'], claimed.pk)


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
            from django.db import connection

            try:
                barrier.wait(timeout=5)
                job = enqueue_generation_job(book.pk)
                results.append(job.pk if job else None)
            finally:
                connection.close()

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
