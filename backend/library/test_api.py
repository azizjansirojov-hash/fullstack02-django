"""API tests for auth, catalog, detail, media gating, and reading progress."""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from .models import Book, BookTranslation, Purchase, ReadingProgress, Review
from .test_auth_helpers import authenticate_jwt

User = get_user_model()


class LibraryAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='apiuser',
            password='Str0ng-Passw0rd!',
            email='apiuser@example.com',
        )
        self.book = Book.objects.create(
            author_name='Ada Lovelace',
            category=Book.Category.SCIENCE,
            published_year=1843,
            slug='api-analytical-engine',
            is_published=True,
            rights_status=Book.RightsStatus.LICENSED,
            pdf_file=SimpleUploadedFile(
                'sample.pdf',
                b'%PDF-1.4 sample',
                content_type='application/pdf',
            ),
            audio_file=SimpleUploadedFile(
                'sample.mp3',
                b'ID3fakeaudio',
                content_type='audio/mpeg',
            ),
        )
        BookTranslation.objects.create(
            book=self.book,
            language=BookTranslation.Language.UZ,
            title='API kitob',
            summary='Qisqa.',
            body='Birinchi bob.\n\nIkkinchi bob.',
        )
        Purchase.objects.create(
            user=self.user,
            book=self.book,
            status=Purchase.Status.PAID,
        )

    def _login(self, user=None):
        """Authenticate via JWT cookies without hitting the login throttle."""
        user = user or self.user
        return authenticate_jwt(self.client, user)

    def _logout(self):
        self.client.cookies.clear()

    def test_catalog_anonymous_hides_media_urls(self):
        response = self.client.get(reverse('library_api:catalog'))
        self.assertEqual(response.status_code, 200)
        shelf = response.json()['shelf']
        self.assertTrue(shelf)
        card = next(item for item in shelf if item['slug'] == self.book.slug)
        self.assertEqual(card['pdf_url'], '')
        self.assertEqual(card['audio_url'], '')
        self.assertTrue(card['has_pdf'])
        self.assertTrue(card['has_audio'])
        self.assertFalse(card['pdf_url'].startswith('/media/books'))

    def test_catalog_authenticated_returns_gated_urls(self):
        self._login()
        response = self.client.get(reverse('library_api:catalog'))
        self.assertEqual(response.status_code, 200)
        card = next(
            item for item in response.json()['shelf'] if item['slug'] == self.book.slug
        )
        self.assertTrue(card['pdf_url'].startswith('/library/media/'))
        self.assertIn('/pdf/', card['pdf_url'])
        self.assertNotIn('/media/books/', card['pdf_url'])

    def test_catalog_activity_timestamps_from_progress(self):
        self._login()
        empty = self.client.get(reverse('library_api:catalog'))
        self.assertEqual(empty.json()['activity_timestamps'], [])

        ReadingProgress.objects.create(
            user=self.user,
            book=self.book,
            mode=ReadingProgress.Mode.FLIP,
            page=1,
        )
        response = self.client.get(reverse('library_api:catalog'))
        stamps = response.json()['activity_timestamps']
        self.assertEqual(len(stamps), 1)
        self.assertTrue(stamps[0])

    def test_catalog_activity_timestamps_capped_at_50_most_recent(self):
        from datetime import timedelta

        from django.utils import timezone

        from .api_views import ACTIVITY_TIMESTAMPS_LIMIT

        self._login()
        base = timezone.now()
        books = []
        for i in range(ACTIVITY_TIMESTAMPS_LIMIT + 5):
            book = Book.objects.create(
                author_name=f'Author {i}',
                slug=f'activity-cap-{i}',
                is_published=True,
                rights_status=Book.RightsStatus.PUBLIC_DOMAIN,
                pdf_generation_status='ready',
                audio_generation_status='ready',
            )
            BookTranslation.objects.create(
                book=book,
                language=BookTranslation.Language.UZ,
                title=f'Title {i}',
                body='Matn.',
            )
            books.append(book)
            row = ReadingProgress.objects.create(
                user=self.user,
                book=book,
                status=ReadingProgress.Status.READING,
                page=1,
            )
            ReadingProgress.objects.filter(pk=row.pk).update(
                updated_at=base - timedelta(minutes=i)
            )

        stamps = self.client.get(reverse('library_api:catalog')).json()[
            'activity_timestamps'
        ]
        self.assertEqual(len(stamps), ACTIVITY_TIMESTAMPS_LIMIT)
        # Most recent first (i=0 is newest).
        parsed = [s for s in stamps]
        self.assertEqual(parsed, sorted(parsed, reverse=True))

    def test_catalog_empty_when_unpublished(self):
        Book.objects.update(is_published=False)
        response = self.client.get(reverse('library_api:catalog'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['is_empty'])
        self.assertEqual(data['shelf'], [])

    def test_catalog_guests_can_browse(self):
        response = self.client.get(reverse('library_api:catalog'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['can_read'])
        card = next(item for item in data['shelf'] if item['slug'] == self.book.slug)
        self.assertEqual(card['title'], 'API kitob')
        self.assertEqual(card['author_name'], 'Ada Lovelace')

    def test_catalog_category_filter(self):
        fantasy = Book.objects.create(
            author_name='Story Weaver',
            category=Book.Category.FANTASY,
            slug='api-ember-crown',
            is_published=True,
            rights_status=Book.RightsStatus.LICENSED,
            pdf_generation_status='ready',
            audio_generation_status='ready',
        )
        BookTranslation.objects.create(
            book=fantasy,
            language=BookTranslation.Language.UZ,
            title='Olov toji',
            summary='Fantaziya.',
            body='Bir paytlar olov.',
        )
        response = self.client.get(
            reverse('library_api:catalog'),
            {'category': Book.Category.SCIENCE},
        )
        self.assertEqual(response.status_code, 200)
        slugs = {item['slug'] for item in response.json()['shelf']}
        self.assertIn(self.book.slug, slugs)
        self.assertNotIn(fantasy.slug, slugs)
        self.assertEqual(response.json()['category'], Book.Category.SCIENCE)

    def test_catalog_search_finds_title(self):
        fantasy = Book.objects.create(
            author_name='Story Weaver',
            category=Book.Category.FANTASY,
            slug='api-search-crown',
            is_published=True,
            rights_status=Book.RightsStatus.LICENSED,
            pdf_generation_status='ready',
            audio_generation_status='ready',
        )
        BookTranslation.objects.create(
            book=fantasy,
            language=BookTranslation.Language.UZ,
            title='Olov toji',
            summary='Fantaziya.',
            body='Bir paytlar olov.',
        )
        response = self.client.get(reverse('library_api:catalog'), {'q': 'Olov'})
        self.assertEqual(response.status_code, 200)
        slugs = {item['slug'] for item in response.json()['shelf']}
        self.assertIn(fantasy.slug, slugs)
        self.assertNotIn(self.book.slug, slugs)

    def test_catalog_excludes_books_without_body(self):
        empty_book = Book.objects.create(
            author_name='Empty Shelf',
            slug='api-empty-shelf',
            is_published=True,
            rights_status=Book.RightsStatus.LICENSED,
            pdf_generation_status='ready',
            audio_generation_status='ready',
        )
        BookTranslation.objects.create(
            book=empty_book,
            language=BookTranslation.Language.UZ,
            title='Should Not Appear',
            body='',
        )

        response = self.client.get(reverse('library_api:catalog'))
        self.assertEqual(response.status_code, 200)
        titles = {item['title'] for item in response.json()['shelf']}
        self.assertNotIn('Should Not Appear', titles)

    def test_detail_requires_auth(self):
        url = reverse('library_api:book-detail', kwargs={'slug': self.book.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 401)

    def test_detail_authenticated(self):
        self._login()
        url = reverse('library_api:book-detail', kwargs={'slug': self.book.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['slug'], self.book.slug)
        self.assertTrue(data['pdf_url'].startswith('/library/media/'))

    def test_reader_manifest_requires_auth(self):
        url = reverse('library_api:reader-manifest', kwargs={'slug': self.book.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 401)

    def test_reader_manifest_includes_body_and_sync(self):
        self.book.translations.filter(language=BookTranslation.Language.UZ).update(
            audio_sync=[{'start': 0.0, 'end': 2.5, 'index': 0, 'text': 'Birinchi.'}],
        )
        self._login()
        url = reverse('library_api:reader-manifest', kwargs={'slug': self.book.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['title'], 'API kitob')
        self.assertIn('Birinchi bob.', data['body'])
        self.assertEqual(len(data['audio_sync']), 1)
        self.assertTrue(data['pdf_url'].startswith('/library/media/'))
        self.assertTrue(data['audio_chapters'])
        self.assertIn('duration_seconds', data['audio_chapters'][0])
        self.assertTrue(data['has_access'])
        self.assertTrue(data['sentence_wrap'])

    def test_reader_manifest_body_is_sanitized_against_script(self):
        """Malicious HTML saved into body must not pass through unescaped."""
        uz = self.book.translations.get(language=BookTranslation.Language.UZ)
        uz.body = 'Intro.\n\n<script>alert(1)</script><p>Safe</p>'
        uz.save()
        uz.refresh_from_db()
        self.assertNotIn('<script', uz.body.lower())

        self._login()
        url = reverse('library_api:reader-manifest', kwargs={'slug': self.book.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        body = response.json()['body']
        self.assertNotIn('<script', body.lower())
        self.assertIn('Intro.', body)
        self.assertIn('Safe', body)

    def test_reader_manifest_denied_without_purchase(self):
        other = User.objects.create_user(
            username='nopurchase',
            password='Str0ng-Passw0rd!',
            email='nopurchase@example.com',
        )
        self._login(other)
        url = reverse('library_api:reader-manifest', kwargs={'slug': self.book.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        self.assertIn('Purchase required', response.json()['detail'])

    def test_media_pdf_requires_auth(self):
        url = reverse('library:book-media-pdf', kwargs={'slug': self.book.slug})
        response = self.client.get(url)
        self.assertIn(response.status_code, (302, 401))

    def test_media_pdf_authenticated(self):
        self._login()
        url = reverse('library:book-media-pdf', kwargs={'slug': self.book.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_raw_media_books_not_served(self):
        response = self.client.get(f'/media/{self.book.pdf_file.name}')
        self.assertEqual(response.status_code, 404)

    def test_reading_progress_roundtrip(self):
        self._login()
        url = reverse(
            'library_api:reading-progress', kwargs={'slug': self.book.slug}
        )
        empty = self.client.get(url)
        self.assertEqual(empty.status_code, 200)
        self.assertFalse(empty.json()['exists'])

        saved = self.client.put(
            url,
            data={'mode': 'flip', 'page': 3, 'position': 0, 'total_pages': 13},
            content_type='application/json',
        )
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()['page'], 3)
        self.assertEqual(saved.json()['total_pages'], 13)
        self.assertTrue(
            ReadingProgress.objects.filter(user=self.user, book=self.book).exists()
        )

        again = self.client.get(url)
        self.assertEqual(again.json()['page'], 3)
        self.assertEqual(again.json()['total_pages'], 13)
        self.assertEqual(again.json()['status'], ReadingProgress.Status.READING)

    def test_flip_save_preserves_listen_audio_bookmark(self):
        """Django flip/pdf sends position:0; must not wipe React listen progress."""
        self._login()
        url = reverse(
            'library_api:reading-progress', kwargs={'slug': self.book.slug}
        )
        self.client.put(
            url,
            data={
                'mode': 'listen',
                'page': 0,
                'position': 12.5,
                'chapter_id': 42,
            },
            content_type='application/json',
        )
        flip_save = self.client.put(
            url,
            data={'mode': 'flip', 'page': 5, 'position': 0, 'total_pages': 20},
            content_type='application/json',
        )
        self.assertEqual(flip_save.status_code, 200)
        data = flip_save.json()
        self.assertEqual(data['mode'], 'flip')
        self.assertEqual(data['page'], 5)
        self.assertEqual(data['position'], 12.5)
        self.assertEqual(data['chapter_id'], 42)

    def test_pdf_save_preserves_listen_audio_bookmark(self):
        """PDF progress PUT must not wipe React listen position/chapter_id."""
        self._login()
        url = reverse(
            'library_api:reading-progress', kwargs={'slug': self.book.slug}
        )
        self.client.put(
            url,
            data={
                'mode': 'listen',
                'page': 0,
                'position': 12.5,
                'chapter_id': 42,
            },
            content_type='application/json',
        )
        pdf_save = self.client.put(
            url,
            data={'mode': 'pdf', 'page': 7, 'position': 0, 'total_pages': 30},
            content_type='application/json',
        )
        self.assertEqual(pdf_save.status_code, 200)
        data = pdf_save.json()
        self.assertEqual(data['mode'], 'pdf')
        self.assertEqual(data['page'], 7)
        self.assertEqual(data['position'], 12.5)
        self.assertEqual(data['chapter_id'], 42)

    def test_listen_save_preserves_flip_page(self):
        """Listen PUT must not wipe a newer flip/pdf page from a stale client page."""
        self._login()
        url = reverse(
            'library_api:reading-progress', kwargs={'slug': self.book.slug}
        )
        self.client.put(
            url,
            data={'mode': 'flip', 'page': 5, 'total_pages': 20, 'position': 0},
            content_type='application/json',
        )
        listen_save = self.client.put(
            url,
            data={
                'mode': 'listen',
                'page': 0,
                'position': 12.5,
                'chapter_id': 42,
            },
            content_type='application/json',
        )
        self.assertEqual(listen_save.status_code, 200)
        data = listen_save.json()
        self.assertEqual(data['mode'], 'listen')
        self.assertEqual(data['page'], 5)
        self.assertEqual(data['total_pages'], 20)
        self.assertEqual(data['position'], 12.5)
        self.assertEqual(data['chapter_id'], 42)

    def test_clear_audio_flag_wipes_listen_bookmark(self):
        self._login()
        url = reverse(
            'library_api:reading-progress', kwargs={'slug': self.book.slug}
        )
        self.client.put(
            url,
            data={'mode': 'listen', 'page': 0, 'position': 9.0, 'chapter_id': 3},
            content_type='application/json',
        )
        cleared = self.client.put(
            url,
            data={
                'mode': 'flip',
                'page': 0,
                'position': 0,
                'chapter_id': None,
                'clear_audio': True,
            },
            content_type='application/json',
        )
        self.assertEqual(cleared.status_code, 200)
        self.assertEqual(cleared.json()['position'], 0.0)
        self.assertIsNone(cleared.json()['chapter_id'])

    def test_add_and_remove_planned(self):
        self._login()
        status_url = reverse(
            'library_api:reading-status', kwargs={'slug': self.book.slug}
        )
        my_url = reverse('library_api:my-library')

        added = self.client.put(
            status_url,
            data={'status': 'planned'},
            content_type='application/json',
        )
        self.assertEqual(added.status_code, 200)
        self.assertEqual(added.json()['status'], 'planned')

        mine = self.client.get(my_url)
        self.assertEqual(mine.status_code, 200)
        data = mine.json()
        self.assertEqual(data['counts']['planned'], 1)
        self.assertEqual(data['counts']['reading'], 0)
        self.assertEqual(len(data['planned']), 1)
        self.assertEqual(data['planned'][0]['slug'], self.book.slug)

        removed = self.client.delete(status_url)
        self.assertEqual(removed.status_code, 200)
        self.assertFalse(removed.json()['exists'])
        self.assertFalse(
            ReadingProgress.objects.filter(user=self.user, book=self.book).exists()
        )
        after = self.client.get(my_url).json()
        self.assertEqual(after['counts']['planned'], 0)
        self.assertEqual(after['planned'], [])

    def test_planned_does_not_downgrade_reading(self):
        self._login()
        ReadingProgress.objects.create(
            user=self.user,
            book=self.book,
            status=ReadingProgress.Status.READING,
            page=2,
        )
        status_url = reverse(
            'library_api:reading-status', kwargs={'slug': self.book.slug}
        )
        response = self.client.put(
            status_url,
            data={'status': 'planned'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'reading')
        self.assertEqual(
            ReadingProgress.objects.get(user=self.user, book=self.book).status,
            ReadingProgress.Status.READING,
        )

    def test_progress_promotes_planned_to_reading(self):
        self._login()
        ReadingProgress.objects.create(
            user=self.user,
            book=self.book,
            status=ReadingProgress.Status.PLANNED,
        )
        progress_url = reverse(
            'library_api:reading-progress', kwargs={'slug': self.book.slug}
        )
        saved = self.client.put(
            progress_url,
            data={'mode': 'flip', 'page': 1, 'position': 0},
            content_type='application/json',
        )
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()['status'], 'reading')

        mine = self.client.get(reverse('library_api:my-library')).json()
        self.assertEqual(mine['counts']['planned'], 0)
        self.assertEqual(mine['counts']['reading'], 1)
        catalog = self.client.get(reverse('library_api:catalog')).json()
        slugs = {item['slug'] for item in catalog['continue_reading']}
        self.assertIn(self.book.slug, slugs)

    def test_mark_finished_and_undo(self):
        self._login()
        ReadingProgress.objects.create(
            user=self.user,
            book=self.book,
            status=ReadingProgress.Status.READING,
            page=5,
            total_pages=10,
        )
        status_url = reverse(
            'library_api:reading-status', kwargs={'slug': self.book.slug}
        )
        finished = self.client.put(
            status_url,
            data={'status': 'finished'},
            content_type='application/json',
        )
        self.assertEqual(finished.status_code, 200)
        self.assertEqual(finished.json()['status'], 'finished')
        self.assertEqual(finished.json()['page'], 5)

        mine = self.client.get(reverse('library_api:my-library')).json()
        self.assertEqual(mine['counts']['finished'], 1)
        self.assertEqual(mine['counts']['reading'], 0)
        catalog = self.client.get(reverse('library_api:catalog')).json()
        slugs = {item['slug'] for item in catalog['continue_reading']}
        self.assertNotIn(self.book.slug, slugs)

        undo = self.client.put(
            status_url,
            data={'status': 'reading'},
            content_type='application/json',
        )
        self.assertEqual(undo.status_code, 200)
        self.assertEqual(undo.json()['status'], 'reading')
        self.assertEqual(
            ReadingProgress.objects.get(user=self.user, book=self.book).page,
            5,
        )

    def test_delete_finished_rejected(self):
        self._login()
        ReadingProgress.objects.create(
            user=self.user,
            book=self.book,
            status=ReadingProgress.Status.FINISHED,
        )
        status_url = reverse(
            'library_api:reading-status', kwargs={'slug': self.book.slug}
        )
        response = self.client.delete(status_url)
        self.assertEqual(response.status_code, 400)
        self.assertTrue(
            ReadingProgress.objects.filter(user=self.user, book=self.book).exists()
        )

    def test_progress_keeps_finished_unless_reopen(self):
        self._login()
        ReadingProgress.objects.create(
            user=self.user,
            book=self.book,
            status=ReadingProgress.Status.FINISHED,
            page=9,
            total_pages=10,
        )
        progress_url = reverse(
            'library_api:reading-progress', kwargs={'slug': self.book.slug}
        )
        ping = self.client.put(
            progress_url,
            data={'mode': 'flip', 'page': 9, 'position': 0, 'total_pages': 10},
            content_type='application/json',
        )
        self.assertEqual(ping.json()['status'], 'finished')

        reopen = self.client.put(
            progress_url,
            data={
                'mode': 'flip',
                'page': 0,
                'position': 0,
                'reopen': True,
            },
            content_type='application/json',
        )
        self.assertEqual(reopen.json()['status'], 'reading')

    def test_my_library_permission_isolation(self):
        other = User.objects.create_user(
            username='otheruser',
            password='Str0ng-Passw0rd!',
            email='other@example.com',
        )
        ReadingProgress.objects.create(
            user=other,
            book=self.book,
            status=ReadingProgress.Status.PLANNED,
        )
        ReadingProgress.objects.create(
            user=self.user,
            book=self.book,
            status=ReadingProgress.Status.READING,
            page=1,
        )

        # Other user's planned book must not appear for self.user
        self._login()
        mine = self.client.get(reverse('library_api:my-library')).json()
        self.assertEqual(mine['counts']['planned'], 0)
        self.assertEqual(mine['counts']['reading'], 1)
        self.assertEqual(mine['planned'], [])

        # Switch identity — other user only sees their own planned row.
        self._login(other)
        other_mine = self.client.get(reverse('library_api:my-library')).json()
        self.assertEqual(other_mine['counts']['planned'], 1)
        self.assertEqual(other_mine['counts']['reading'], 0)
        self.assertNotEqual(
            ReadingProgress.objects.get(user=self.user, book=self.book).status,
            ReadingProgress.Status.PLANNED,
        )

    def test_activity_timestamps_exclude_planned(self):
        self._login()
        ReadingProgress.objects.create(
            user=self.user,
            book=self.book,
            status=ReadingProgress.Status.PLANNED,
        )
        response = self.client.get(reverse('library_api:catalog'))
        self.assertEqual(response.json()['activity_timestamps'], [])

    def test_detail_includes_reading_status(self):
        self._login()
        ReadingProgress.objects.create(
            user=self.user,
            book=self.book,
            status=ReadingProgress.Status.FINISHED,
        )
        url = reverse('library_api:book-detail', kwargs={'slug': self.book.slug})
        data = self.client.get(url).json()
        self.assertEqual(data['reading_status'], 'finished')

    def test_my_library_requires_auth(self):
        response = self.client.get(reverse('library_api:my-library'))
        self.assertEqual(response.status_code, 401)


class AuthAPIExtraTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='refreshuser',
            password='Str0ng-Passw0rd!',
            email='refresh@example.com',
        )

    def test_token_refresh(self):
        login = self.client.post(
            reverse('users:api-login'),
            data={'username': 'refreshuser', 'password': 'Str0ng-Passw0rd!'},
            content_type='application/json',
        )
        self.assertEqual(login.status_code, 200)
        self.assertIn('refresh_token', login.cookies)

        refresh = self.client.post(
            reverse('users:api-token-refresh'),
            data={},
            content_type='application/json',
        )
        self.assertEqual(refresh.status_code, 200)
        self.assertIn('access_token', refresh.cookies)

    def test_me_anonymous(self):
        response = self.client.get(reverse('users:api-me'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['authenticated'])

    def test_me_authenticated(self):
        self.client.post(
            reverse('users:api-login'),
            data={'username': 'refreshuser', 'password': 'Str0ng-Passw0rd!'},
            content_type='application/json',
        )
        response = self.client.get(reverse('users:api-me'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['authenticated'])
        self.assertEqual(response.json()['user']['username'], 'refreshuser')


class SimilarBooksAPITests(TestCase):
    """BookDetailAPIView includes same-category recommendations (similar_books)."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='simuser',
            password='Str0ng-Passw0rd!',
            email='simuser@example.com',
        )
        pdf = SimpleUploadedFile('b.pdf', b'%PDF-1.4 x', content_type='application/pdf')
        self.book = Book.objects.create(
            author_name='Author A',
            category=Book.Category.FICTION,
            slug='sim-main-book',
            is_published=True,
            rights_status=Book.RightsStatus.PUBLIC_DOMAIN,
            pdf_generation_status='ready',
            audio_generation_status='ready',
            pdf_file=pdf,
        )
        BookTranslation.objects.create(
            book=self.book,
            language=BookTranslation.Language.UZ,
            title='Asosiy kitob',
            body='Matn.',
        )
        # Same category — should appear in similar_books
        self.similar = Book.objects.create(
            author_name='Author B',
            category=Book.Category.FICTION,
            slug='sim-similar-book',
            is_published=True,
            rights_status=Book.RightsStatus.PUBLIC_DOMAIN,
            pdf_generation_status='ready',
            audio_generation_status='ready',
        )
        BookTranslation.objects.create(
            book=self.similar,
            language=BookTranslation.Language.UZ,
            title="O'xshash kitob",
            body='Matn.',
        )
        # Different category — must NOT appear
        self.other_category = Book.objects.create(
            author_name='Author C',
            category=Book.Category.SCIENCE,
            slug='sim-other-category',
            is_published=True,
            rights_status=Book.RightsStatus.PUBLIC_DOMAIN,
            pdf_generation_status='ready',
            audio_generation_status='ready',
        )
        BookTranslation.objects.create(
            book=self.other_category,
            language=BookTranslation.Language.UZ,
            title='Boshqa janr',
            body='Matn.',
        )

    def _login(self):
        authenticate_jwt(self.client, self.user)

    def test_similar_books_present_in_detail(self):
        self._login()
        url = reverse('library_api:book-detail', kwargs={'slug': self.book.slug})
        data = self.client.get(url).json()
        self.assertIn('similar_books', data)
        slugs = [b['slug'] for b in data['similar_books']]
        self.assertIn(self.similar.slug, slugs)

    def test_current_book_excluded_from_similar(self):
        self._login()
        url = reverse('library_api:book-detail', kwargs={'slug': self.book.slug})
        data = self.client.get(url).json()
        slugs = [b['slug'] for b in data['similar_books']]
        self.assertNotIn(self.book.slug, slugs)

    def test_different_category_excluded(self):
        self._login()
        url = reverse('library_api:book-detail', kwargs={'slug': self.book.slug})
        data = self.client.get(url).json()
        slugs = [b['slug'] for b in data['similar_books']]
        self.assertNotIn(self.other_category.slug, slugs)

    def test_similar_books_capped_at_four(self):
        """Never return more than 4 similar books."""
        for i in range(6):
            b = Book.objects.create(
                author_name=f'Extra {i}',
                category=Book.Category.FICTION,
                slug=f'sim-extra-{i}',
                is_published=True,
                rights_status=Book.RightsStatus.PUBLIC_DOMAIN,
                pdf_generation_status='ready',
                audio_generation_status='ready',
            )
            BookTranslation.objects.create(
                book=b, language=BookTranslation.Language.UZ,
                title=f'Extra {i}', body='x.',
            )
        self._login()
        url = reverse('library_api:book-detail', kwargs={'slug': self.book.slug})
        data = self.client.get(url).json()
        self.assertLessEqual(len(data['similar_books']), 4)

    def test_empty_similar_books_when_no_same_category(self):
        """Book with unique category returns empty similar_books list."""
        unique = Book.objects.create(
            author_name='Solo',
            category=Book.Category.POETRY,
            slug='sim-unique-poetry',
            is_published=True,
            rights_status=Book.RightsStatus.PUBLIC_DOMAIN,
            pdf_generation_status='ready',
            audio_generation_status='ready',
        )
        BookTranslation.objects.create(
            book=unique, language=BookTranslation.Language.UZ,
            title='Yagona she\'r', body='Matn.',
        )
        self._login()
        url = reverse('library_api:book-detail', kwargs={'slug': unique.slug})
        data = self.client.get(url).json()
        self.assertEqual(data['similar_books'], [])


class ReviewAPITests(TestCase):
    """Tests for ReviewAPIView and review_count/average_rating on book detail."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username='reviewer1',
            password='Str0ng-Passw0rd!',
            email='reviewer1@example.com',
        )
        self.other = User.objects.create_user(
            username='reviewer2',
            password='Str0ng-Passw0rd!',
            email='reviewer2@example.com',
        )
        pdf = SimpleUploadedFile('r.pdf', b'%PDF-1.4 x', content_type='application/pdf')
        self.book = Book.objects.create(
            author_name='Review Author',
            category=Book.Category.FICTION,
            slug='review-test-book',
            is_published=True,
            rights_status=Book.RightsStatus.PUBLIC_DOMAIN,
            pdf_generation_status='ready',
            audio_generation_status='ready',
            pdf_file=pdf,
        )
        BookTranslation.objects.create(
            book=self.book,
            language=BookTranslation.Language.UZ,
            title='Sharh sinov kitob',
            body='Matn.',
        )
        self.unpublished = Book.objects.create(
            author_name='Hidden Author',
            slug='review-hidden-book',
            is_published=False,
            rights_status=Book.RightsStatus.PUBLIC_DOMAIN,
        )
        self.reviews_url = reverse(
            'library_api:book-reviews', kwargs={'slug': self.book.slug}
        )
        self.detail_url = reverse(
            'library_api:book-detail', kwargs={'slug': self.book.slug}
        )

    def _login(self, user=None):
        authenticate_jwt(self.client, user or self.user)

    # ── GET (public) ──────────────────────────────────────────────────────────

    def test_anonymous_can_list_empty_reviews(self):
        response = self.client.get(self.reviews_url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 0)
        self.assertIsNone(data['average_rating'])
        self.assertEqual(data['results'], [])
        self.assertEqual(data['pagination']['page'], 1)
        self.assertEqual(data['pagination']['num_pages'], 1)
        self.assertFalse(data['pagination']['has_next'])
        self.assertNotIn('my_review', data)

    def test_list_shows_reviews_and_average(self):
        Review.objects.create(user=self.user, book=self.book, rating=4, text='Good')
        Review.objects.create(user=self.other, book=self.book, rating=2, text='Meh')
        response = self.client.get(self.reviews_url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 2)
        self.assertEqual(data['average_rating'], 3.0)
        usernames = {r['username'] for r in data['results']}
        self.assertIn('reviewer1', usernames)
        self.assertIn('reviewer2', usernames)
        self.assertEqual(len(data['results']), 2)
        self.assertEqual(data['pagination']['page'], 1)
        self.assertFalse(data['pagination']['has_next'])

    def test_reviews_pagination_caps_page_size_at_20(self):
        users = [
            User.objects.create_user(
                username=f'revpage{i}',
                password='Str0ng-Passw0rd!',
                email=f'revpage{i}@example.com',
            )
            for i in range(25)
        ]
        for i, user in enumerate(users):
            Review.objects.create(user=user, book=self.book, rating=5, text=f'r{i}')

        page1 = self.client.get(self.reviews_url).json()
        self.assertEqual(page1['count'], 25)
        self.assertEqual(len(page1['results']), 20)
        self.assertEqual(page1['pagination']['page'], 1)
        self.assertEqual(page1['pagination']['num_pages'], 2)
        self.assertTrue(page1['pagination']['has_next'])
        self.assertEqual(page1['pagination']['next_page'], 2)
        self.assertIsNone(page1['pagination']['previous_page'])

        page2 = self.client.get(f'{self.reviews_url}?page=2').json()
        self.assertEqual(len(page2['results']), 5)
        self.assertEqual(page2['pagination']['page'], 2)
        self.assertTrue(page2['pagination']['has_previous'])
        self.assertEqual(page2['pagination']['previous_page'], 1)
        self.assertFalse(page2['pagination']['has_next'])

        ids1 = {r['id'] for r in page1['results']}
        ids2 = {r['id'] for r in page2['results']}
        self.assertFalse(ids1 & ids2)

    def test_authenticated_my_review_even_when_not_on_first_page(self):
        """Additive my_review is present when own review is older than page 1."""
        from datetime import timedelta

        from django.utils import timezone

        self._login()
        mine = Review.objects.create(
            user=self.user, book=self.book, rating=3, text='mine-old'
        )
        Review.objects.filter(pk=mine.pk).update(
            created_at=timezone.now() - timedelta(days=30)
        )
        for i in range(20):
            u = User.objects.create_user(
                username=f'newer{i}',
                password='Str0ng-Passw0rd!',
                email=f'newer{i}@example.com',
            )
            Review.objects.create(user=u, book=self.book, rating=5, text=f'n{i}')

        response = self.client.get(self.reviews_url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['results']), 20)
        self.assertNotIn('reviewer1', {r['username'] for r in data['results']})
        self.assertIsNotNone(data.get('my_review'))
        self.assertEqual(data['my_review']['username'], 'reviewer1')
        self.assertEqual(data['my_review']['text'], 'mine-old')

    def test_reviews_not_exposed_for_unpublished_book(self):
        url = reverse('library_api:book-reviews', kwargs={'slug': self.unpublished.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    # ── POST ──────────────────────────────────────────────────────────────────

    def test_anonymous_cannot_post(self):
        response = self.client.post(
            self.reviews_url,
            data={'rating': 5, 'text': 'Great'},
            content_type='application/json',
        )
        # CSRF enforcement fires first for unauthenticated state-changing requests
        self.assertIn(response.status_code, (401, 403))

    def test_authenticated_can_create_review(self):
        self._login()
        response = self.client.post(
            self.reviews_url,
            data={'rating': 5, 'text': 'Excellent!'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data['rating'], 5)
        self.assertEqual(data['text'], 'Excellent!')
        self.assertEqual(data['username'], 'reviewer1')
        self.assertTrue(Review.objects.filter(user=self.user, book=self.book).exists())

    def test_rating_below_1_rejected(self):
        self._login()
        response = self.client.post(
            self.reviews_url,
            data={'rating': 0},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Review.objects.filter(user=self.user, book=self.book).exists())

    def test_rating_above_5_rejected(self):
        self._login()
        response = self.client.post(
            self.reviews_url,
            data={'rating': 6},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_missing_rating_rejected(self):
        self._login()
        response = self.client.post(
            self.reviews_url,
            data={'text': 'No rating'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_text_over_2000_chars_rejected(self):
        self._login()
        response = self.client.post(
            self.reviews_url,
            data={'rating': 4, 'text': 'x' * 2001},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('2000', response.json()['detail'])
        self.assertFalse(Review.objects.filter(user=self.user, book=self.book).exists())

    def test_text_at_2000_chars_accepted(self):
        self._login()
        response = self.client.post(
            self.reviews_url,
            data={'rating': 3, 'text': 'y' * 2000},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(response.json()['text']), 2000)

    def test_duplicate_review_rejected(self):
        Review.objects.create(user=self.user, book=self.book, rating=3)
        self._login()
        response = self.client.post(
            self.reviews_url,
            data={'rating': 5, 'text': 'Trying again'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('PUT', response.json()['detail'])
        # Original review untouched
        self.assertEqual(Review.objects.get(user=self.user, book=self.book).rating, 3)

    def test_duplicate_review_integrity_error_is_handled_as_400(self):
        self._login()
        with (
            patch('library.api.reviews.Review.objects.filter') as mock_filter,
            patch(
                'library.api.reviews.Review.objects.create',
                side_effect=IntegrityError('unique_user_book_review'),
            ),
        ):
            mock_filter.return_value.exists.return_value = False
            response = self.client.post(
                self.reviews_url,
                data={'rating': 5, 'text': 'Race condition'},
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn('PUT', response.json()['detail'])

    def test_review_write_throttle_returns_429_after_limit(self):
        self._login()
        with patch(
            'rest_framework.throttling.ScopedRateThrottle.get_rate',
            return_value='2/min',
        ):
            first = self.client.post(
                self.reviews_url,
                data={'rating': 5, 'text': 'First'},
                content_type='application/json',
            )
            second = self.client.put(
                self.reviews_url,
                data={'rating': 4, 'text': 'Second'},
                content_type='application/json',
            )
            third = self.client.put(
                self.reviews_url,
                data={'rating': 3, 'text': 'Third should be throttled'},
                content_type='application/json',
            )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(third.status_code, 429)

    # ── PUT ───────────────────────────────────────────────────────────────────

    def test_authenticated_can_update_own_review(self):
        Review.objects.create(user=self.user, book=self.book, rating=3, text='OK')
        self._login()
        response = self.client.put(
            self.reviews_url,
            data={'rating': 5, 'text': 'Changed my mind!'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['rating'], 5)
        self.assertEqual(
            Review.objects.get(user=self.user, book=self.book).rating, 5
        )

    def test_put_returns_404_when_no_existing_review(self):
        self._login()
        response = self.client.put(
            self.reviews_url,
            data={'rating': 4},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)

    def test_user_cannot_update_another_users_review(self):
        """PUT only affects the caller's own review, not others'."""
        other_review = Review.objects.create(
            user=self.other, book=self.book, rating=2, text='Not great'
        )
        self._login()  # logged in as self.user, not self.other
        response = self.client.put(
            self.reviews_url,
            data={'rating': 1, 'text': 'Trying to overwrite'},
            content_type='application/json',
        )
        # user has no review → 404, other's review untouched
        self.assertEqual(response.status_code, 404)
        other_review.refresh_from_db()
        self.assertEqual(other_review.rating, 2)

    # ── DELETE ────────────────────────────────────────────────────────────────

    def test_authenticated_can_delete_own_review(self):
        Review.objects.create(user=self.user, book=self.book, rating=4)
        self._login()
        response = self.client.delete(self.reviews_url)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Review.objects.filter(user=self.user, book=self.book).exists())

    def test_delete_returns_404_when_no_review(self):
        self._login()
        response = self.client.delete(self.reviews_url)
        self.assertEqual(response.status_code, 404)

    def test_user_cannot_delete_another_users_review(self):
        other_review = Review.objects.create(
            user=self.other, book=self.book, rating=5
        )
        self._login()
        response = self.client.delete(self.reviews_url)
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Review.objects.filter(pk=other_review.pk).exists())

    # ── Book detail aggregation ───────────────────────────────────────────────

    def test_book_detail_has_zero_reviews_by_default(self):
        self._login()
        data = self.client.get(self.detail_url).json()
        self.assertEqual(data['review_count'], 0)
        self.assertIsNone(data['average_rating'])

    def test_book_detail_average_rating_reflects_reviews(self):
        Review.objects.create(user=self.user, book=self.book, rating=4)
        Review.objects.create(user=self.other, book=self.book, rating=2)
        self._login()
        data = self.client.get(self.detail_url).json()
        self.assertEqual(data['review_count'], 2)
        self.assertEqual(data['average_rating'], 3.0)

    def test_catalog_shelf_includes_review_aggregates(self):
        Review.objects.create(user=self.user, book=self.book, rating=5)
        Review.objects.create(user=self.other, book=self.book, rating=3)
        self._login()
        catalog = self.client.get(reverse('library_api:catalog')).json()
        card = next(item for item in catalog['shelf'] if item['slug'] == self.book.slug)
        self.assertEqual(card['review_count'], 2)
        self.assertEqual(card['average_rating'], 4.0)

    def test_continue_reading_includes_review_aggregates(self):
        Review.objects.create(user=self.user, book=self.book, rating=4)
        ReadingProgress.objects.create(
            user=self.user,
            book=self.book,
            status=ReadingProgress.Status.READING,
            page=1,
        )
        self._login()
        catalog = self.client.get(reverse('library_api:catalog')).json()
        card = next(
            item for item in catalog['continue_reading'] if item['slug'] == self.book.slug
        )
        self.assertEqual(card['review_count'], 1)
        self.assertEqual(card['average_rating'], 4.0)

    def test_review_text_is_visible_to_other_users_via_get(self):
        """User A's comment text must appear in GET for User B (and guests)."""
        Review.objects.create(
            user=self.user,
            book=self.book,
            rating=5,
            text='Foydalanuvchi A sharhi',
        )
        # Guest can read reviews (AllowAny GET)
        guest = self.client.get(self.reviews_url)
        self.assertEqual(guest.status_code, 200)
        texts = [r['text'] for r in guest.json()['results']]
        self.assertIn('Foydalanuvchi A sharhi', texts)

        # A different authenticated user also sees it
        self.client.logout()
        authenticate_jwt(self.client, self.other)
        other = self.client.get(self.reviews_url)
        self.assertEqual(other.status_code, 200)
        other_texts = [r['text'] for r in other.json()['results']]
        self.assertIn('Foydalanuvchi A sharhi', other_texts)
