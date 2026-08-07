"""Reading progress and shelf-status API views."""

from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.authentication import CSRFEnforcedAuthentication, JWTCookieAuthentication

from ..activity import record_reading_session
from ..models import Book, ReadingProgress
from ..serializers import ProgressUpsertSerializer
from ._common import serialize_progress_payload

class ReadingProgressAPIView(APIView):
    """Get or upsert the current user's reading progress for a book."""

    permission_classes = [IsAuthenticated]
    authentication_classes = [
        CSRFEnforcedAuthentication,
        JWTCookieAuthentication,
    ]

    def get(self, request, slug):
        book = get_object_or_404(Book, slug=slug, is_published=True)
        progress = ReadingProgress.objects.filter(user=request.user, book=book).first()
        if not progress:
            return Response({'exists': False, 'status': None})
        return Response(serialize_progress_payload(progress))

    def put(self, request, slug):
        return self._upsert(request, slug)

    def post(self, request, slug):
        return self._upsert(request, slug)

    def _upsert(self, request, slug):
        book = get_object_or_404(Book, slug=slug, is_published=True)
        serializer = ProgressUpsertSerializer(data=request.data)
        if not serializer.is_valid():
            if 'status' in serializer.errors:
                return Response(
                    {'detail': 'Invalid status.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        mode = data['mode']
        page = data['page']
        total_pages = data['total_pages']
        chapter_id = data['chapter_id']
        position = data['position']
        reopen = data['reopen']
        clear_audio = data['clear_audio']
        requested_status = data['status']
        minutes_delta = data.get('minutes_delta')

        existing = ReadingProgress.objects.filter(user=request.user, book=book).first()
        previous_heartbeat_at = existing.updated_at if existing else None
        previous_page = existing.page if existing else None
        next_status = ReadingProgress.Status.READING
        if existing:
            if existing.status == ReadingProgress.Status.PLANNED:
                next_status = ReadingProgress.Status.READING
            elif existing.status == ReadingProgress.Status.FINISHED:
                if reopen or requested_status == ReadingProgress.Status.READING:
                    next_status = ReadingProgress.Status.READING
                else:
                    next_status = ReadingProgress.Status.FINISHED
            else:
                next_status = ReadingProgress.Status.READING
                if requested_status == ReadingProgress.Status.READING:
                    next_status = ReadingProgress.Status.READING
        elif requested_status == ReadingProgress.Status.READING or reopen:
            next_status = ReadingProgress.Status.READING

        defaults = {
            'mode': mode,
            'status': next_status,
        }

        # Listen owns audio bookmark but must not clobber flip/pdf page from a stale client.
        # Flip/pdf own page but must not clobber React listen position/chapter_id.
        if mode == ReadingProgress.Mode.LISTEN:
            defaults['chapter_id'] = chapter_id
            defaults['position'] = position
            if existing:
                defaults['page'] = existing.page
                if existing.total_pages is not None:
                    defaults['total_pages'] = existing.total_pages
            else:
                defaults['page'] = page
                if total_pages is not None:
                    defaults['total_pages'] = total_pages
        elif clear_audio:
            defaults['page'] = page
            defaults['chapter_id'] = chapter_id
            defaults['position'] = position
            if total_pages is not None:
                defaults['total_pages'] = total_pages
        else:
            defaults['page'] = page
            if total_pages is not None:
                defaults['total_pages'] = total_pages
            if existing:
                defaults['chapter_id'] = existing.chapter_id
                defaults['position'] = existing.position
            else:
                defaults['chapter_id'] = chapter_id
                defaults['position'] = position

        progress, _created = ReadingProgress.objects.update_or_create(
            user=request.user,
            book=book,
            defaults=defaults,
        )
        if next_status == ReadingProgress.Status.READING:
            pages_delta = 0
            new_page = defaults.get('page')
            if (
                mode != ReadingProgress.Mode.LISTEN
                and previous_page is not None
                and new_page is not None
                and new_page > previous_page
            ):
                pages_delta = new_page - previous_page
            record_reading_session(
                request.user,
                minutes_delta=minutes_delta,
                pages_delta=pages_delta,
                previous_heartbeat_at=previous_heartbeat_at,
            )
        return Response(serialize_progress_payload(progress), status=status.HTTP_200_OK)


class ReadingStatusAPIView(APIView):
    """Set or remove the user's shelf status for a book (planned / reading / finished)."""

    permission_classes = [IsAuthenticated]
    authentication_classes = [
        CSRFEnforcedAuthentication,
        JWTCookieAuthentication,
    ]

    def put(self, request, slug):
        book = get_object_or_404(Book, slug=slug, is_published=True)
        new_status = request.data.get('status')
        if new_status not in ReadingProgress.Status.values:
            return Response(
                {'detail': 'Invalid status. Use planned, reading, or finished.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        progress = ReadingProgress.objects.filter(user=request.user, book=book).first()

        if new_status == ReadingProgress.Status.PLANNED:
            if progress and progress.status in (
                ReadingProgress.Status.READING,
                ReadingProgress.Status.FINISHED,
            ):
                # Do not downgrade — return current status unchanged.
                return Response(serialize_progress_payload(progress))
            progress, _ = ReadingProgress.objects.update_or_create(
                user=request.user,
                book=book,
                defaults={
                    'status': ReadingProgress.Status.PLANNED,
                    'mode': ReadingProgress.Mode.FLIP,
                    'page': 0,
                    'position': 0,
                    'chapter_id': None,
                },
            )
            return Response(serialize_progress_payload(progress))

        if progress:
            update_fields = ['status', 'updated_at']
            if (
                new_status == ReadingProgress.Status.FINISHED
                and progress.finished_at is None
            ):
                progress.finished_at = timezone.now()
                update_fields.append('finished_at')
            progress.status = new_status
            progress.save(update_fields=update_fields)
        else:
            create_kwargs = {
                'user': request.user,
                'book': book,
                'status': new_status,
            }
            if new_status == ReadingProgress.Status.FINISHED:
                create_kwargs['finished_at'] = timezone.now()
            progress = ReadingProgress.objects.create(**create_kwargs)
        return Response(serialize_progress_payload(progress))

    def delete(self, request, slug):
        book = get_object_or_404(Book, slug=slug, is_published=True)
        progress = ReadingProgress.objects.filter(user=request.user, book=book).first()
        if not progress:
            return Response({'exists': False, 'status': None})
        if progress.status != ReadingProgress.Status.PLANNED:
            return Response(
                {
                    'detail': (
                        'DELETE only removes planned books. '
                        'Use PUT status=reading to undo finished.'
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        progress.delete()
        return Response({'exists': False, 'status': None}, status=status.HTTP_200_OK)


