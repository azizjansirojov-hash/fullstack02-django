"""Django admin for the Uzbek book library."""

from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from .models import Book, BookTranslation


class BookTranslationInline(admin.StackedInline):
    model = BookTranslation
    extra = 1
    max_num = 1
    fields = ('language', 'title', 'summary', 'why_read', 'body', 'audio_sync')
    verbose_name = 'Uzbek content'
    verbose_name_plural = 'Uzbek content (required before publishing)'


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = (
        'display_title',
        'author_name',
        'category',
        'published_year',
        'is_published',
        'translation_count',
        'created_at',
    )
    list_filter = ('is_published', 'category', 'published_year')
    search_fields = ('slug', 'author_name', 'translations__title')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [BookTranslationInline]
    fieldsets = (
        (
            None,
            {
                'fields': (
                    'author_name',
                    'category',
                    'slug',
                    'cover_image',
                    'pdf_file',
                    'audio_file',
                    'published_year',
                    'is_published',
                ),
                'description': (
                    'Assign a category so the title appears on its own shelf list. '
                    'Add Uzbek content below before publishing.'
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
        return super().get_queryset(request).prefetch_related('translations')

    @admin.display(description='Title')
    def display_title(self, obj):
        translation = obj.get_translation(BookTranslation.Language.UZ)
        return translation.title if translation else obj.slug

    @admin.display(description='Content')
    def translation_count(self, obj):
        codes = sorted(obj.translations.values_list('language', flat=True))
        return ', '.join(c.upper() for c in codes) if codes else '—'

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
        if book.is_published:
            if not book.pdf_file:
                messages.warning(
                    request,
                    'This published book has no PDF file. PDF mode and download will be disabled.',
                )
            if not book.audio_file:
                messages.warning(
                    request,
                    'This published book has no audio file. Listen mode will be disabled.',
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
