"""DRF serializers for library API payloads and write validation.

Output helpers wrap the existing serialize_* functions so entitlement URL
gating in serialize_book_card stays the single source of truth.
"""

from rest_framework import serializers

from .models import Notification, ReadingProgress, Review


class BookCardSerializer(serializers.Serializer):
    """Read-only shelf/card shape — populated from serialize_book_card dicts."""

    slug = serializers.CharField()
    author_name = serializers.CharField(allow_blank=True)
    category = serializers.CharField()
    category_label = serializers.CharField()
    published_year = serializers.IntegerField(allow_null=True)
    cover_url = serializers.CharField(allow_blank=True)
    has_pdf = serializers.BooleanField()
    has_audio = serializers.BooleanField()
    has_access = serializers.BooleanField()
    rights_status = serializers.CharField()
    pdf_generation_status = serializers.CharField()
    audio_generation_status = serializers.CharField()
    pdf_url = serializers.CharField(allow_blank=True)
    read_url = serializers.CharField()
    audio_url = serializers.CharField(allow_blank=True)
    audio_duration_seconds = serializers.IntegerField(allow_null=True)
    title = serializers.CharField()
    summary = serializers.CharField(allow_blank=True)
    average_rating = serializers.FloatField(required=False, allow_null=True)
    review_count = serializers.IntegerField(required=False)
    reading_status = serializers.CharField(required=False, allow_null=True)


class ReviewSerializer(serializers.ModelSerializer):
    """Public review payload (matches serialize_review)."""

    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Review
        fields = (
            'id',
            'username',
            'rating',
            'text',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields


class ReviewWriteSerializer(serializers.Serializer):
    """Validate create/update review body."""

    rating = serializers.IntegerField(min_value=1, max_value=5)
    text = serializers.CharField(required=False, allow_blank=True, max_length=2000, default='')

    def validate_text(self, value):
        return (value or '').strip()


class NotificationSerializer(serializers.ModelSerializer):
    """Current user's notification payload."""

    book_slug = serializers.CharField(source='book.slug', read_only=True, allow_null=True)

    class Meta:
        model = Notification
        fields = (
            'id',
            'message',
            'type',
            'is_read',
            'link_url',
            'book_slug',
            'created_at',
        )
        read_only_fields = fields


class ProgressPayloadSerializer(serializers.Serializer):
    """Read-only progress payload (matches serialize_progress_payload)."""

    exists = serializers.BooleanField()
    status = serializers.CharField(allow_null=True)
    mode = serializers.CharField(required=False)
    page = serializers.IntegerField(required=False)
    total_pages = serializers.IntegerField(required=False, allow_null=True)
    chapter_id = serializers.IntegerField(required=False, allow_null=True)
    position = serializers.FloatField(required=False)
    updated_at = serializers.DateTimeField(required=False)


class ProgressUpsertSerializer(serializers.Serializer):
    """Parse progress PUT/POST body while preserving lenient defaults."""

    mode = serializers.CharField(required=False, allow_blank=True, default='')
    page = serializers.IntegerField(required=False, default=0)
    total_pages = serializers.IntegerField(required=False, allow_null=True, default=None)
    chapter_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    position = serializers.FloatField(required=False, default=0.0)
    reopen = serializers.BooleanField(required=False, default=False)
    clear_audio = serializers.BooleanField(required=False, default=False)
    status = serializers.CharField(required=False, allow_blank=True, allow_null=True, default=None)

    def to_internal_value(self, data):
        # Accept partial / loosely typed clients (legacy SPA / tests).
        raw = data if hasattr(data, 'get') else {}
        mode = raw.get('mode') or ReadingProgress.Mode.FLIP
        if mode not in ReadingProgress.Mode.values:
            mode = ReadingProgress.Mode.FLIP
        try:
            page = int(raw.get('page', 0) or 0)
        except (TypeError, ValueError):
            page = 0
        page = max(0, page)
        total_pages = raw.get('total_pages', None)
        if total_pages in ('', None):
            total_pages = None
        else:
            try:
                total_pages = max(1, int(total_pages))
            except (TypeError, ValueError):
                total_pages = None
        chapter_id = raw.get('chapter_id', None)
        if chapter_id in ('', None):
            chapter_id = None
        else:
            try:
                chapter_id = int(chapter_id)
            except (TypeError, ValueError):
                chapter_id = None
        try:
            position = float(raw.get('position', 0) or 0)
        except (TypeError, ValueError):
            position = 0.0
        requested_status = raw.get('status')
        if requested_status is not None and requested_status not in ReadingProgress.Status.values:
            raise serializers.ValidationError({'status': 'Invalid status.'})
        minutes_delta = raw.get('minutes_delta', None)
        if minutes_delta in ('', None):
            minutes_delta = None
        else:
            try:
                minutes_delta = int(minutes_delta)
            except (TypeError, ValueError):
                minutes_delta = None
            else:
                minutes_delta = max(0, min(15, minutes_delta))
        return {
            'mode': mode,
            'page': page,
            'total_pages': total_pages,
            'chapter_id': chapter_id,
            'position': position,
            'reopen': bool(raw.get('reopen')),
            'clear_audio': bool(raw.get('clear_audio')),
            'status': requested_status,
            'minutes_delta': minutes_delta,
        }
