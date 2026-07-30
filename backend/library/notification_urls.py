"""Notification API routes mounted under /api/notifications/."""

from django.urls import path

from . import notification_views

app_name = 'notifications'

urlpatterns = [
    path('', notification_views.NotificationListAPIView.as_view(), name='list'),
    path(
        '<int:notification_id>/read/',
        notification_views.NotificationReadAPIView.as_view(),
        name='read',
    ),
    path(
        'read-all/',
        notification_views.NotificationReadAllAPIView.as_view(),
        name='read-all',
    ),
]
