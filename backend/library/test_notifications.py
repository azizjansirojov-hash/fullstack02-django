"""Tests for in-app notifications and their delivery triggers."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .models import Book, Notification, Purchase, ReadingProgress
from .notifications import notify_audio_ready

User = get_user_model()


class NotificationAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='reader', password='testpass123')
        self.other_user = User.objects.create_user(
            username='other-reader',
            password='testpass123',
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_list_empty(self):
        response = self.client.get(reverse('notifications:list'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results'], [])
        self.assertEqual(response.data['count'], 0)
        self.assertEqual(response.data['unread_count'], 0)

    def test_list_notifications_and_unread_count(self):
        Notification.objects.create(
            user=self.user,
            message='Birinchi',
            type=Notification.Type.AUDIO_READY,
        )
        Notification.objects.create(
            user=self.user,
            message='Ikkinchi',
            type=Notification.Type.PURCHASE_PAID,
            is_read=True,
        )
        Notification.objects.create(
            user=self.other_user,
            message='Boshqa foydalanuvchi',
            type=Notification.Type.AUDIO_READY,
        )

        response = self.client.get(reverse('notifications:list'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(response.data['unread_count'], 1)
        self.assertEqual({row['message'] for row in response.data['results']}, {'Birinchi', 'Ikkinchi'})

    def test_mark_one_read(self):
        notification = Notification.objects.create(
            user=self.user,
            message='O‘qilmagan',
            type=Notification.Type.AUDIO_READY,
        )

        response = self.client.post(
            reverse('notifications:read', kwargs={'notification_id': notification.pk})
        )

        self.assertEqual(response.status_code, 200)
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_mark_all_read(self):
        Notification.objects.create(
            user=self.user,
            message='Birinchi',
            type=Notification.Type.AUDIO_READY,
        )
        Notification.objects.create(
            user=self.user,
            message='Ikkinchi',
            type=Notification.Type.PURCHASE_PAID,
        )

        response = self.client.post(reverse('notifications:read-all'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['unread_count'], 0)
        self.assertFalse(Notification.objects.filter(user=self.user, is_read=False).exists())

    def test_anonymous_request_is_unauthorized(self):
        anonymous_client = APIClient()

        response = anonymous_client.get(reverse('notifications:list'))

        self.assertEqual(response.status_code, 401)


class NotificationTriggerTests(TestCase):
    def setUp(self):
        self.book = Book.objects.create(author_name='Author', slug='notification-book')
        self.reader = User.objects.create_user(username='reader', password='testpass123')
        self.planned = User.objects.create_user(username='planned', password='testpass123')
        self.finished = User.objects.create_user(username='finished', password='testpass123')

    def test_audio_ready_notifies_only_reading_users(self):
        ReadingProgress.objects.create(
            user=self.reader,
            book=self.book,
            status=ReadingProgress.Status.READING,
        )
        ReadingProgress.objects.create(
            user=self.planned,
            book=self.book,
            status=ReadingProgress.Status.PLANNED,
        )
        ReadingProgress.objects.create(
            user=self.finished,
            book=self.book,
            status=ReadingProgress.Status.FINISHED,
        )

        notify_audio_ready(self.book)

        notifications = Notification.objects.filter(type=Notification.Type.AUDIO_READY)
        self.assertEqual(list(notifications.values_list('user_id', flat=True)), [self.reader.pk])

    def test_purchase_payment_creates_notification_once_on_status_change(self):
        purchase = Purchase.objects.create(
            user=self.reader,
            book=self.book,
            status=Purchase.Status.PENDING,
        )
        purchase.status = Purchase.Status.PAID
        purchase.save()
        purchase.save()

        notifications = Notification.objects.filter(
            user=self.reader,
            type=Notification.Type.PURCHASE_PAID,
        )
        self.assertEqual(notifications.count(), 1)
        self.assertEqual(notifications.first().book, self.book)
