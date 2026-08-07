"""Tests for daily reading goal / ReadingSession activity stats."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from library.models import Book, BookTranslation, Purchase, ReadingSession
from library.test_auth_helpers import authenticate_jwt
from users.models import UserPreferences

User = get_user_model()


class DailyGoalActivityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='goaluser',
            password='Str0ng-Passw0rd!',
            email='goaluser@example.com',
        )
        self.book = Book.objects.create(
            author_name='Goal Author',
            slug='goal-book',
            is_published=True,
            rights_status=Book.RightsStatus.PUBLIC_DOMAIN,
            pdf_generation_status='ready',
            audio_generation_status='ready',
        )
        BookTranslation.objects.create(
            book=self.book,
            language=BookTranslation.Language.UZ,
            title='Goal kitob',
            body='Matn.',
        )
        Purchase.objects.create(
            user=self.user,
            book=self.book,
            status=Purchase.Status.PAID,
        )

    def _login(self):
        return authenticate_jwt(self.client, self.user)

    def test_catalog_activity_stats_zero_activity_defaults(self):
        self._login()
        data = self.client.get(reverse('library_api:catalog')).json()
        stats = data['activity_stats']
        self.assertEqual(stats['today_minutes_read'], 0)
        self.assertEqual(stats['daily_goal_minutes'], 20)
        self.assertEqual(stats['goal_progress_percent'], 0)
        self.assertEqual(stats['week_minutes_total'], 0)
        self.assertEqual(stats['week_pages_total'], 0)
        self.assertEqual(stats['badges'], [])

    def test_catalog_activity_stats_goal_exactly_met(self):
        self._login()
        ReadingSession.objects.create(
            user=self.user,
            date=timezone.localdate(),
            minutes_read=20,
        )
        stats = self.client.get(reverse('library_api:catalog')).json()['activity_stats']
        self.assertEqual(stats['today_minutes_read'], 20)
        self.assertEqual(stats['daily_goal_minutes'], 20)
        self.assertEqual(stats['goal_progress_percent'], 100)

    def test_catalog_activity_stats_respects_custom_goal(self):
        self._login()
        UserPreferences.objects.create(user=self.user, daily_goal_minutes=40)
        ReadingSession.objects.create(
            user=self.user,
            date=timezone.localdate(),
            minutes_read=10,
        )
        stats = self.client.get(reverse('library_api:catalog')).json()['activity_stats']
        self.assertEqual(stats['daily_goal_minutes'], 40)
        self.assertEqual(stats['goal_progress_percent'], 25)

    def test_progress_upsert_with_minutes_delta_updates_session(self):
        self._login()
        url = reverse('library_api:reading-progress', kwargs={'slug': self.book.slug})
        response = self.client.put(
            url,
            data={'mode': 'flip', 'page': 1, 'minutes_delta': 5},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        session = ReadingSession.objects.get(user=self.user, date=timezone.localdate())
        self.assertEqual(session.minutes_read, 5)

        # Legitimate spaced heartbeat (≥50s, ≤IDLE_GAP wall-clock bound).
        ReadingSession.objects.filter(pk=session.pk).update(
            updated_at=timezone.now() - timedelta(minutes=15),
        )
        self.client.put(
            url,
            data={'mode': 'flip', 'page': 2, 'minutes_delta': 15},
            content_type='application/json',
        )
        session.refresh_from_db()
        self.assertEqual(session.minutes_read, 20)

    def test_rapid_minutes_delta_does_not_inflate_beyond_wall_clock(self):
        """Rapid-fire minutes_delta:15 must not stack full 15m chunks."""
        from library.activity import record_reading_session

        session = record_reading_session(self.user, minutes_delta=15)
        self.assertEqual(session.minutes_read, 15)
        for _ in range(10):
            record_reading_session(self.user, minutes_delta=15)
        session.refresh_from_db()
        self.assertEqual(session.minutes_read, 15)

    def test_daily_minutes_ceiling_enforced(self):
        from library.activity import MAX_DAILY_READING_MINUTES, record_reading_session

        today = timezone.localdate()
        session = ReadingSession.objects.create(
            user=self.user,
            date=today,
            minutes_read=MAX_DAILY_READING_MINUTES - 10,
        )
        ReadingSession.objects.filter(pk=session.pk).update(
            updated_at=timezone.now() - timedelta(minutes=15),
        )
        record_reading_session(self.user, minutes_delta=15)
        session.refresh_from_db()
        self.assertEqual(session.minutes_read, MAX_DAILY_READING_MINUTES)

        ReadingSession.objects.filter(pk=session.pk).update(
            updated_at=timezone.now() - timedelta(minutes=15),
        )
        record_reading_session(self.user, minutes_delta=15)
        session.refresh_from_db()
        self.assertEqual(session.minutes_read, MAX_DAILY_READING_MINUTES)

    def test_spaced_minutes_delta_still_accumulates(self):
        from library.activity import record_reading_session

        session = record_reading_session(self.user, minutes_delta=5)
        self.assertEqual(session.minutes_read, 5)
        ReadingSession.objects.filter(pk=session.pk).update(
            updated_at=timezone.now() - timedelta(minutes=5),
        )
        # Wall-clock bound: 5 elapsed minutes → at most +5 even if client claims 15.
        record_reading_session(self.user, minutes_delta=15)
        session.refresh_from_db()
        self.assertEqual(session.minutes_read, 10)
        ReadingSession.objects.filter(pk=session.pk).update(
            updated_at=timezone.now() - timedelta(minutes=10),
        )
        record_reading_session(self.user, minutes_delta=10)
        session.refresh_from_db()
        self.assertEqual(session.minutes_read, 20)

    def test_preferences_put_bounds(self):
        self._login()
        url = reverse('users:api-preferences')
        ok = self.client.put(
            url,
            data={'daily_goal_minutes': 30},
            content_type='application/json',
        )
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json()['daily_goal_minutes'], 30)

        low = self.client.put(
            url,
            data={'daily_goal_minutes': 4},
            content_type='application/json',
        )
        self.assertEqual(low.status_code, 400)

        high = self.client.put(
            url,
            data={'daily_goal_minutes': 301},
            content_type='application/json',
        )
        self.assertEqual(high.status_code, 400)

    @override_settings(TIME_ZONE='Asia/Tashkent', USE_TZ=True)
    def test_session_date_uses_localdate_timezone_boundary(self):
        """Near UTC midnight should land on Asia/Tashkent local calendar date."""
        from unittest.mock import patch

        self._login()
        utc = ZoneInfo('UTC')
        # 2026-03-15 23:30 UTC == 2026-03-16 04:30 in Asia/Tashkent (+05)
        frozen = datetime(2026, 3, 15, 23, 30, tzinfo=utc)
        with patch('django.utils.timezone.now', return_value=frozen):
            url = reverse(
                'library_api:reading-progress',
                kwargs={'slug': self.book.slug},
            )
            response = self.client.put(
                url,
                data={'mode': 'flip', 'page': 1, 'minutes_delta': 3},
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 200)
        session = ReadingSession.objects.get(user=self.user)
        self.assertEqual(str(session.date), '2026-03-16')
        self.assertEqual(session.minutes_read, 3)

    def test_guest_catalog_activity_stats_null(self):
        data = self.client.get(reverse('library_api:catalog')).json()
        self.assertIsNone(data['activity_stats'])

    def test_catalog_week_stats_sum_last_seven_days(self):
        self._login()
        today = timezone.localdate()
        ReadingSession.objects.create(
            user=self.user,
            date=today,
            minutes_read=10,
            pages_read=4,
        )
        ReadingSession.objects.create(
            user=self.user,
            date=today - timedelta(days=3),
            minutes_read=15,
            pages_read=6,
        )
        # Outside the 7-day window — ignored.
        ReadingSession.objects.create(
            user=self.user,
            date=today - timedelta(days=8),
            minutes_read=100,
            pages_read=100,
        )
        stats = self.client.get(reverse('library_api:catalog')).json()['activity_stats']
        self.assertEqual(stats['week_minutes_total'], 25)
        self.assertEqual(stats['week_pages_total'], 10)

    def test_progress_page_advance_increments_pages_read(self):
        self._login()
        url = reverse('library_api:reading-progress', kwargs={'slug': self.book.slug})
        self.client.put(
            url,
            data={'mode': 'flip', 'page': 2, 'minutes_delta': 1},
            content_type='application/json',
        )
        self.client.put(
            url,
            data={'mode': 'flip', 'page': 5, 'minutes_delta': 1},
            content_type='application/json',
        )
        session = ReadingSession.objects.get(user=self.user, date=timezone.localdate())
        self.assertEqual(session.pages_read, 3)

    def test_badges_highest_streak_only_and_finished_month(self):
        from library.models import ReadingProgress

        self._login()
        today = timezone.localdate()
        for i in range(7):
            ReadingSession.objects.create(
                user=self.user,
                date=today - timedelta(days=i),
                minutes_read=5,
            )
        # A second finished book this month.
        other = Book.objects.create(
            author_name='Other',
            slug='badge-finished-2',
            is_published=True,
            rights_status=Book.RightsStatus.PUBLIC_DOMAIN,
            pdf_generation_status='ready',
            audio_generation_status='ready',
        )
        BookTranslation.objects.create(
            book=other,
            language=BookTranslation.Language.UZ,
            title='Boshqa',
            body='Matn.',
        )
        ReadingProgress.objects.create(
            user=self.user,
            book=self.book,
            status=ReadingProgress.Status.FINISHED,
        )
        ReadingProgress.objects.create(
            user=self.user,
            book=other,
            status=ReadingProgress.Status.FINISHED,
        )
        badges = self.client.get(reverse('library_api:catalog')).json()['activity_stats'][
            'badges'
        ]
        ids = [b['id'] for b in badges]
        self.assertIn('streak_7', ids)
        self.assertNotIn('streak_3', ids)
        self.assertIn('finished_1', ids)
        self.assertNotIn('finished_3', ids)
        self.assertLessEqual(len(badges), 2)

    def test_badges_hidden_when_none_earned(self):
        self._login()
        badges = self.client.get(reverse('library_api:catalog')).json()['activity_stats'][
            'badges'
        ]
        self.assertEqual(badges, [])
