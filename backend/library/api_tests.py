"""API tests for auth, catalog, detail, media gating, and reading progress."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from users.auth import get_tokens_for_user

from .models import Book, BookTranslation, Purchase, ReadingProgress

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
        tokens = get_tokens_for_user(user)
        self.client.cookies[settings.JWT_ACCESS_COOKIE_NAME] = tokens['access']
        self.client.cookies[settings.JWT_REFRESH_COOKIE_NAME] = tokens['refresh']
        return tokens

    def _logout(self):
        self.client.cookies.pop(settings.JWT_ACCESS_COOKIE_NAME, None)
        self.client.cookies.pop(settings.JWT_REFRESH_COOKIE_NAME, None)

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
