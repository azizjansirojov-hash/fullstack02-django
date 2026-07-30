"""Authenticated notification API endpoints."""

from django.shortcuts import get_object_or_404
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.authentication import CSRFEnforcedAuthentication, JWTCookieAuthentication

from .models import Notification
from .serializers import NotificationSerializer


class NotificationPagination(PageNumberPagination):
    page_size = 20


class NotificationListAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTCookieAuthentication]

    def get(self, request):
        queryset = Notification.objects.filter(user=request.user).select_related('book')
        paginator = NotificationPagination()
        page = paginator.paginate_queryset(queryset, request)
        response = paginator.get_paginated_response(
            NotificationSerializer(page, many=True).data
        )
        response.data['unread_count'] = queryset.filter(is_read=False).count()
        return response


class NotificationReadAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CSRFEnforcedAuthentication, JWTCookieAuthentication]

    def post(self, request, notification_id):
        notification = get_object_or_404(
            Notification,
            pk=notification_id,
            user=request.user,
        )
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=['is_read'])
        return Response(NotificationSerializer(notification).data)


class NotificationReadAllAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CSRFEnforcedAuthentication, JWTCookieAuthentication]

    def post(self, request):
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({'unread_count': 0})
