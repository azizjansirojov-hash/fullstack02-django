"""Django admin for the Uzbek book bookstore catalog."""

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.utils.html import format_html

from .generation_health import book_generation_ops_summary
from .jobs import GenerationEnqueueError
from .models import (
    AudioChapter,
    Book,
    BookTranslation,
    GenerationJob,
    Notification,
    Purchase,
    ReadingProgress,
    ReadingSession,
    Review,
)


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('user', 'book', 'status', 'paid_at', 'created_at', 'updated_at')
    list_filter = ('status',)
    search_fields = ('user__username', 'user__email', 'book__slug', 'book__author_name')
    readonly_fields = ('created_at', 'updated_at', 'paid_at')
    autocomplete_fields = ('user', 'book')
    actions = ('action_mark_as_paid',)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related('user', 'book')
            .prefetch_related('book__translations')
        )

    @admin.action(description='Mark selected purchases as paid')
    def action_mark_as_paid(self, request, queryset):
        from django.utils import timezone

        updated = 0
        for purchase in queryset.exclude(status=Purchase.Status.PAID):
            purchase.status = Purchase.Status.PAID
            purchase.paid_at = timezone.now()
            purchase.save(update_fields=['status', 'paid_at', 'updated_at'])
            updated += 1
        self.message_user(
            request,
            f'Marked {updated} purchase(s) as paid.',
            messages.SUCCESS,
        )


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'type', 'message', 'book', 'is_read', 'created_at')
    list_filter = ('type', 'is_read')
    search_fields = ('user__username', 'user__email', 'message', 'book__slug')
    readonly_fields = ('created_at',)
    autocomplete_fields = ('user', 'book')

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related('user', 'book')
            .prefetch_related('book__translations')
        )


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    """Staff moderation for reader ratings and comments."""

    list_display = ('user', 'book', 'rating', 'created_at', 'text_preview')
    list_filter = ('rating',)
    search_fields = (
        'user__username',
        'user__email',
        'book__slug',
        'book__author_name',
        'book__translations__title',
        'text',
    )
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ('user', 'book')

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related('user', 'book')
            .prefetch_related('book__translations')
        )

    @admin.display(description='Text')
    def text_preview(self, obj):
        text = (obj.text or '').strip()
        if len(text) <= 80:
            return text or '—'
        return f'{text[:77]}…'


@admin.register(ReadingProgress)
class ReadingProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'book', 'status', 'mode', 'page', 'chapter_id', 'updated_at')
    list_filter = ('status', 'mode')
    search_fields = ('user__username', 'book__slug')
    readonly_fields = ('updated_at',)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related('user', 'book')
            .prefetch_related('book__translations')
        )


@admin.register(ReadingSession)
class ReadingSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'minutes_read', 'updated_at')
    list_filter = ('date',)
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('updated_at',)
    autocomplete_fields = ('user',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(GenerationJob)
class GenerationJobAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'book',
        'job_type',
        'status',
        'force',
        'attempts',
        'locked_by',
        'updated_at',
        'stale_hint',
    )
    list_filter = ('status', 'job_type')
    search_fields = ('book__slug', 'error_message', 'locked_by')
    readonly_fields = (
        'book',
        'job_type',
        'status',
        'force',
        'attempts',
        'max_attempts',
        'locked_at',
        'locked_by',
        'error_message',
        'created_at',
        'updated_at',
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related('book')
            .prefetch_related('book__translations')
        )

    def has_add_permission(self, request):
        return False

    @admin.display(description='Ops')
    def stale_hint(self, obj):
        from datetime import timedelta

        from django.conf import settings
        from django.utils import timezone
        from django.utils.safestring import mark_safe

        if obj.status != GenerationJob.Status.QUEUED:
            return '—'
        seconds = getattr(settings, 'GENERATION_STALE_QUEUED_SECONDS', 300)
        if obj.created_at < timezone.now() - timedelta(seconds=seconds):
            return mark_safe(
                '<span style="color:#b91c1c;font-weight:600">'
                'STALE — worker likely not running</span>'
            )
        return 'queued (waiting for worker)'


class BookTranslationInline(admin.StackedInline):
    model = BookTranslation
    extra = 1
    max_num = 1
    fields = ('language', 'title', 'summary', 'body', 'audio_sync')
    verbose_name = 'Uzbek content'
    verbose_name_plural = 'Uzbek content (required before publishing)'


class AudioChapterInline(admin.TabularInline):
    """Read-only view of generated (or legacy) audio chapters — no file upload."""

    model = AudioChapter
    extra = 0
    can_delete = False
    fields = (
        'order',
        'title',
        'voice_id',
        'tts_provider',
        'duration_seconds',
        'generated_at',
        'audio_ready',
    )
    readonly_fields = fields
    ordering = ('order',)
    verbose_name = 'Audio chapter'
    verbose_name_plural = 'Audio chapters (auto-generated)'

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description='Audio')
    def audio_ready(self, obj):
        if obj.audio_file:
            return format_html(
                '<a href="{}" target="_blank">Ready</a>',
                obj.book.gated_chapter_audio_url(obj.pk),
            )
        return '—'


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = (
        'display_title',
        'author_name',
        'category',
        'rights_status',
        'published_year',
        'is_published',
        'pdf_generation_status',
        'audio_generation_status',
        'generation_ops_display',
        'translation_count',
        'created_at',
    )
    list_filter = (
        'is_published',
        'rights_status',
        'category',
        'published_year',
        'pdf_generation_status',
        'audio_generation_status',
    )
    search_fields = ('slug', 'author_name', 'translations__title')
    readonly_fields = (
        'created_at',
        'updated_at',
        'pdf_status_display',
        'audio_status_display',
        'generation_ops_display',
        'pdf_generation_status',
        'audio_generation_status',
        'pdf_generated_at',
        'audio_generated_at',
    )
    inlines = [BookTranslationInline, AudioChapterInline]
    actions = ('action_regenerate_pdf', 'action_regenerate_audio', 'action_regenerate_all')
    fieldsets = (
        (
            None,
            {
                'fields': (
                    'author_name',
                    'category',
                    'slug',
                    'cover_image',
                    'published_year',
                    'rights_status',
                    'is_published',
                ),
                'description': (
                    'Checklist before publish: (1) set rights_status to public_domain '
                    'or licensed, (2) add Uzbek body, (3) wait for PDF/audio Ready, '
                    '(4) publish. Generation will not run without rights clearance.'
                ),
            },
        ),
        (
            'Generated media status',
            {
                'fields': (
                    'generation_ops_display',
                    'pdf_status_display',
                    'audio_status_display',
                    'pdf_generation_status',
                    'audio_generation_status',
                    'pdf_generated_at',
                    'audio_generated_at',
                ),
            },
        ),
        (
            'Timestamps',
            {
                'fields': ('created_at', 'updated_at'),
                'classes': ('collapse',),
            },
        ),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .prefetch_related('translations', 'audio_chapters', 'generation_jobs')
        )

    @admin.display(description='Title')
    def display_title(self, obj):
        translation = obj.get_translation(BookTranslation.Language.UZ)
        return translation.title if translation else obj.slug

    @admin.display(description='Content')
    def translation_count(self, obj):
        codes = sorted(obj.translations.values_list('language', flat=True))
        return ', '.join(c.upper() for c in codes) if codes else '—'

    @admin.display(description='Generation ops')
    def generation_ops_display(self, obj):
        from django.utils.safestring import mark_safe

        summary = book_generation_ops_summary(obj)
        parts = []
        if summary['stale']:
            parts.append(
                mark_safe(
                    '<span style="color:#b91c1c;font-weight:600">'
                    'STALE QUEUE — start process_generation_jobs worker</span>'
                )
            )
        elif summary['queued_count']:
            oldest = summary['oldest_queued']
            age = f' (oldest job #{oldest.pk})' if oldest else ''
            parts.append(format_html('queued×{}{}', summary['queued_count'], age))
        if summary['last_failed']:
            err = (summary['last_failed'].error_message or 'failed')[:120]
            parts.append(
                format_html(
                    '<span style="color:#b91c1c">last failure: {}</span>',
                    err,
                )
            )
        if not parts:
            return '—'
        return mark_safe('<br>'.join(str(p) for p in parts))

    @admin.display(description='PDF status')
    def pdf_status_display(self, obj):
        status = obj.pdf_generation_status or 'pending'
        gated = obj.gated_pdf_url()
        if gated:
            return format_html(
                '{} — <a href="{}" target="_blank">Open PDF</a>',
                status,
                gated,
            )
        return status

    @admin.display(description='Audio status')
    def audio_status_display(self, obj):
        status = obj.audio_generation_status or 'pending'
        count = obj.audio_chapters.count()
        if count:
            return f'{status} — {count} track(s)'
        gated = obj.gated_legacy_audio_url()
        if gated:
            return format_html(
                '{} — <a href="{}" target="_blank">Open audio</a>',
                status,
                gated,
            )
        return status

    def save_model(self, request, obj, form, change):
        if not obj.slug:
            uz_title = ''
            for i in range(10):
                prefix = f'translations-{i}-'
                if request.POST.get(f'{prefix}DELETE'):
                    continue
                if request.POST.get(f'{prefix}language') == BookTranslation.Language.UZ:
                    uz_title = request.POST.get(f'{prefix}title', '') or ''
                    break
            obj.ensure_slug(preferred_title=uz_title)
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        book = form.instance
        uz = book.translations.filter(language=BookTranslation.Language.UZ).first()
        if uz and uz.title and not form.cleaned_data.get('slug'):
            book.slug = ''
            book.ensure_slug(preferred_title=uz.title)
            book.save(update_fields=['slug', 'updated_at'])

        if uz and (uz.body or '').strip():
            if book.rights_status in {
                Book.RightsStatus.PUBLIC_DOMAIN,
                Book.RightsStatus.LICENSED,
            }:
                messages.info(
                    request,
                    'Book saved. PDF and audio were queued for the generation worker — '
                    'refresh after the worker runs. If status stays queued, the worker '
                    'is not running (see Generation ops / /health/generation/).',
                )
            else:
                messages.warning(
                    request,
                    'Uzbek body saved, but media was NOT queued: set rights_status to '
                    'public_domain or licensed first.',
                )
        elif book.is_published:
            messages.warning(
                request,
                'Add Uzbek body text so PDF and audio can be generated automatically.',
            )

        try:
            book.full_clean()
        except ValidationError as exc:
            message_dict = getattr(exc, 'message_dict', None)
            if message_dict and 'is_published' in message_dict:
                book.is_published = False
                book.save(update_fields=['is_published', 'updated_at'])
                messages.error(
                    request,
                    message_dict['is_published'][0]
                    if isinstance(message_dict['is_published'], list)
                    else message_dict['is_published'],
                )
                raise
            raise

    def _queue_regenerate(self, request, queryset, job_type, label):
        from .jobs import enqueue_generation_job

        ok = 0
        for book in queryset:
            try:
                enqueue_generation_job(
                    book.pk,
                    job_type=job_type,
                    force=True,
                    user=request.user,
                )
                ok += 1
            except GenerationEnqueueError as exc:
                messages.error(request, f'{book}: {exc}')
        if ok:
            messages.success(request, f'Queued {label} for {ok} book(s).')

    @admin.action(description='Queue PDF regenerate')
    def action_regenerate_pdf(self, request, queryset):
        self._queue_regenerate(
            request, queryset, GenerationJob.JobType.PDF, 'PDF regeneration'
        )

    @admin.action(description='Queue audio regenerate')
    def action_regenerate_audio(self, request, queryset):
        self._queue_regenerate(
            request, queryset, GenerationJob.JobType.AUDIO, 'audio regeneration'
        )

    @admin.action(description='Queue PDF and audio regenerate')
    def action_regenerate_all(self, request, queryset):
        self._queue_regenerate(
            request, queryset, GenerationJob.JobType.ALL, 'full media regeneration'
        )
