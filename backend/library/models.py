"""Book catalog models with Uzbek content translations."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify


class Book(models.Model):
    """Shared metadata for a library title. Content lives in BookTranslation."""

    class Category(models.TextChoices):
        SCIENCE = 'science', 'Science'
        FICTION = 'fiction', 'Fiction'
        NOVEL = 'novel', 'Novels'
        FANTASY = 'fantasy', 'Fantasy'
        HISTORY = 'history', 'History'
        BIOGRAPHY = 'biography', 'Biography'
        POETRY = 'poetry', 'Poetry'
        TECHNOLOGY = 'technology', 'Technology'
        PHILOSOPHY = 'philosophy', 'Philosophy'
        OTHER = 'other', 'Other'

    class RightsStatus(models.TextChoices):
        UNSET = 'unset', 'Not set (blocked)'
        PUBLIC_DOMAIN = 'public_domain', 'Public domain'
        LICENSED = 'licensed', 'Licensed for sale'
        PENDING_CLEARANCE = 'pending_clearance', 'Pending clearance'

    slug = models.SlugField(
        max_length=220,
        unique=True,
        blank=True,
        help_text='URL-friendly identifier. Auto-filled from the Uzbek title if left blank.',
    )
    cover_image = models.ImageField(
        upload_to='covers/',
        blank=True,
        null=True,
        help_text='Optional cover image shown on the shelf and reader.',
    )
    pdf_file = models.FileField(
        upload_to='books/pdf/',
        blank=True,
        null=True,
        help_text='Auto-generated PDF from Uzbek content (legacy uploads preserved).',
    )
    audio_file = models.FileField(
        upload_to='books/audio/',
        blank=True,
        null=True,
        help_text='Legacy single-track audio fallback (prefer AudioChapter tracks).',
    )
    pdf_source_hash = models.CharField(max_length=64, blank=True, default='')
    pdf_generation_status = models.CharField(
        max_length=16,
        choices=[
            ('pending', 'Not generated'),
            ('generating', 'Generating'),
            ('ready', 'Ready'),
            ('failed', 'Failed'),
            ('legacy', 'Legacy upload'),
        ],
        default='pending',
    )
    pdf_generated_at = models.DateTimeField(blank=True, null=True)
    audio_source_hash = models.CharField(max_length=64, blank=True, default='')
    audio_generation_status = models.CharField(
        max_length=16,
        choices=[
            ('pending', 'Not generated'),
            ('generating', 'Generating'),
            ('ready', 'Ready'),
            ('failed', 'Failed'),
            ('legacy', 'Legacy upload'),
        ],
        default='pending',
    )
    audio_generated_at = models.DateTimeField(blank=True, null=True)
    author_name = models.CharField(max_length=200)
    category = models.CharField(
        max_length=32,
        choices=Category.choices,
        default=Category.OTHER,
        db_index=True,
        help_text='Keeps each title on its own shelf direction.',
    )
    rights_status = models.CharField(
        max_length=32,
        choices=RightsStatus.choices,
        default=RightsStatus.UNSET,
        db_index=True,
        help_text=(
            'Bookstore rights clearance. Public domain or licensed required '
            'before PDF/TTS generation and publishing.'
        ),
    )
    published_year = models.PositiveSmallIntegerField(blank=True, null=True)
    is_published = models.BooleanField(
        default=False,
        help_text=(
            'Published books appear on the public shelf. '
            'Requires an Uzbek translation.'
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', 'author_name']

    def __str__(self):
        uz = self.translations.filter(language=BookTranslation.Language.UZ).first()
        if uz:
            return f'{uz.title} — {self.author_name}'
        return f'{self.author_name} ({self.slug})'

    def ensure_slug(self, preferred_title=''):
        """Assign a unique slug from preferred_title or author_name when blank."""
        if self.slug:
            return
        base = slugify(preferred_title) or slugify(self.author_name) or 'book'
        candidate = base
        counter = 2
        while Book.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
            candidate = f'{base}-{counter}'
            counter += 1
        self.slug = candidate

    def clean(self):
        super().clean()
        if self.is_published and self.pk:
            if self.rights_status not in {
                self.RightsStatus.PUBLIC_DOMAIN,
                self.RightsStatus.LICENSED,
            }:
                raise ValidationError(
                    {
                        'is_published': (
                            'Cannot publish until rights_status is public_domain '
                            f'or licensed (current={self.rights_status}).'
                        ),
                    }
                )
            languages = set(self.translations.values_list('language', flat=True))
            missing = [
                code.upper()
                for code, _label in BookTranslation.Language.choices
                if code not in languages
            ]
            if missing:
                raise ValidationError(
                    {
                        'is_published': (
                            f'Cannot publish until translations exist for: '
                            f'{", ".join(missing)}. '
                            'Add Uzbek content below.'
                        ),
                    }
                )
            ready = {'ready', 'legacy'}
            pdf_ok = (self.pdf_generation_status or 'pending') in ready
            audio_ok = (self.audio_generation_status or 'pending') in ready
            if not pdf_ok or not audio_ok:
                raise ValidationError(
                    {
                        'is_published': (
                            'Cannot publish until PDF and audio generation are '
                            f'ready (PDF={self.pdf_generation_status or "pending"}, '
                            f'audio={self.audio_generation_status or "pending"}). '
                            'Save with body text, wait for the worker, then publish.'
                        ),
                    }
                )

    def save(self, *args, **kwargs):
        self.ensure_slug()
        if self.is_published and self.pk:
            self.clean()
        super().save(*args, **kwargs)

    def get_translation(self, language=None):
        """Return Uzbek translation, or any available translation as fallback."""
        if language is None:
            language = BookTranslation.Language.UZ
        translations = {t.language: t for t in self.translations.all()}
        if language in translations:
            return translations[language]
        if BookTranslation.Language.UZ in translations:
            return translations[BookTranslation.Language.UZ]
        if translations:
            return next(iter(translations.values()))
        return None

    def gated_pdf_url(self):
        """Auth-gated PDF path (empty when no PDF). Never a raw /media/books URL."""
        if not self.pdf_file:
            return ''
        from django.urls import reverse

        return reverse('library:book-media-pdf', kwargs={'slug': self.slug})

    def gated_legacy_audio_url(self):
        """Auth-gated legacy audio path (empty when no legacy file)."""
        if not self.audio_file:
            return ''
        from django.urls import reverse

        return reverse('library:book-media-audio', kwargs={'slug': self.slug})

    def gated_chapter_audio_url(self, chapter_id):
        from django.urls import reverse

        return reverse(
            'library:book-media-chapter-audio',
            kwargs={'slug': self.slug, 'chapter_id': chapter_id},
        )

    def get_audio_chapters_payload(self, *, include_urls=True):
        """Playlist for the reader: AudioChapter rows, else legacy audio_file.

        When include_urls is False (anonymous API), url fields are empty strings
        so clients never receive working file paths.
        """
        chapters = list(self.audio_chapters.all())
        if chapters:
            return [
                {
                    'id': chapter.id,
                    'title': chapter.title or f'{index + 1}-qism',
                    'url': (
                        self.gated_chapter_audio_url(chapter.id) if include_urls else ''
                    ),
                    'order': chapter.order,
                }
                for index, chapter in enumerate(chapters)
            ]
        if self.audio_file:
            return [
                {
                    'id': None,
                    'title': '1-qism',
                    'url': self.gated_legacy_audio_url() if include_urls else '',
                    'order': 0,
                }
            ]
        return []

    def has_audio(self):
        """True when listen mode has at least one playable track."""
        if self.audio_chapters.exclude(audio_file='').filter(audio_file__isnull=False).exists():
            return True
        # FileField empty string vs null
        if self.audio_chapters.exclude(audio_file='').exists():
            return True
        return bool(self.audio_file)

    def has_pdf(self):
        return bool(self.pdf_file)

    def total_audio_duration_seconds(self):
        """Sum of chapter durations when known; None if no usable durations."""
        chapters = list(self.audio_chapters.all())
        if not chapters:
            return None
        total = 0
        any_known = False
        for chapter in chapters:
            if chapter.duration_seconds:
                total += chapter.duration_seconds
                any_known = True
        return total if any_known else None


class AudioChapter(models.Model):
    """One narrated track/chapter for a book (auto-generated TTS or legacy upload)."""

    book = models.ForeignKey(
        Book,
        related_name='audio_chapters',
        on_delete=models.CASCADE,
    )
    title = models.CharField(
        max_length=255,
        blank=True,
        help_text="e.g. '1-bob' or chapter name. Optional.",
    )
    order = models.PositiveIntegerField(
        default=0,
        help_text='Playback order, lower number plays first.',
    )
    audio_file = models.FileField(
        upload_to='books/audio/',
        blank=True,
        null=True,
        help_text='Generated or legacy audio file for this track.',
    )
    duration_seconds = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text='Optional, for display purposes.',
    )
    source_text = models.TextField(
        blank=True,
        default='',
        help_text='Text segment this track was generated from.',
    )
    source_text_hash = models.CharField(max_length=64, blank=True, default='')
    tts_provider = models.CharField(max_length=64, blank=True, default='')
    voice_id = models.CharField(
        max_length=128,
        blank=True,
        default='uz-UZ-MadinaNeural',
        help_text='TTS voice id (default: female Uzbek Madina).',
    )
    generated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        label = self.title or f'Track {self.order}'
        return f'{self.book} — {label}'


class BookTranslation(models.Model):
    """Localized title, body, and summary for a book (Uzbek)."""

    class Language(models.TextChoices):
        UZ = 'uz', 'Uzbek'

    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name='translations',
    )
    language = models.CharField(
        max_length=2,
        choices=Language.choices,
        default=Language.UZ,
    )
    title = models.CharField(max_length=300)
    summary = models.TextField(
        blank=True,
        default='',
        help_text='Optional short blurb for catalog cards.',
    )
    why_read = models.TextField(
        blank=True,
        default='',
        help_text='Optional note for the reader (not shown on public pages).',
    )
    body = models.TextField(
        help_text='Full readable text. Separate paragraphs with blank lines.',
    )
    audio_sync = models.JSONField(
        blank=True,
        default=list,
        help_text='Optional sentence-level timing metadata for audio sync.',
    )

    class Meta:
        ordering = ['language']
        constraints = [
            models.UniqueConstraint(
                fields=['book', 'language'],
                name='unique_book_language',
            ),
        ]

    def __str__(self):
        return f'{self.title} ({self.get_language_display()})'

    def clean(self):
        super().clean()
        data = self.audio_sync
        if not data:
            return
        if not isinstance(data, list):
            raise ValidationError({'audio_sync': 'Must be a JSON array.'})
        for index, row in enumerate(data):
            if not isinstance(row, dict):
                raise ValidationError(
                    {'audio_sync': f'Row {index} must be an object.'}
                )
            for key in ('start', 'end'):
                if key not in row:
                    raise ValidationError(
                        {'audio_sync': f'Row {index} is missing "{key}".'}
                    )
                if not isinstance(row[key], (int, float)):
                    raise ValidationError(
                        {'audio_sync': f'Row {index} "{key}" must be a number.'}
                    )
            if 'index' in row and not isinstance(row['index'], (int, float)):
                raise ValidationError(
                    {'audio_sync': f'Row {index} "index" must be a number.'}
                )
            if 'text' in row and not isinstance(row['text'], str):
                raise ValidationError(
                    {'audio_sync': f'Row {index} "text" must be a string.'}
                )


class ReadingProgress(models.Model):
    """Per-user reading position and shelf status for a book."""

    class Mode(models.TextChoices):
        FLIP = 'flip', 'Flip'
        PDF = 'pdf', 'PDF'
        LISTEN = 'listen', 'Listen'

    class Status(models.TextChoices):
        PLANNED = 'planned', 'Planned'
        READING = 'reading', 'Reading'
        FINISHED = 'finished', 'Finished'

    user = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='reading_progress',
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name='reading_progress',
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.READING,
        db_index=True,
    )
    mode = models.CharField(
        max_length=16,
        choices=Mode.choices,
        default=Mode.FLIP,
    )
    page = models.PositiveIntegerField(
        default=0,
        help_text='Zero-based page index for flip/pdf modes.',
    )
    total_pages = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text='Last known total page count for flip/pdf (for progress %).',
    )
    chapter_id = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text='Audio chapter id when mode is listen.',
    )
    position = models.FloatField(
        default=0,
        help_text='Audio seconds or fine-grained offset within the page.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'book'],
                name='unique_user_book_progress',
            ),
        ]
        indexes = [
            models.Index(
                fields=['user', 'status', '-updated_at'],
                name='library_rp_user_status_upd',
            ),
        ]

    def __str__(self):
        return f'{self.user_id}:{self.book_id} {self.status} {self.mode}@{self.page}'


class Purchase(models.Model):
    """Entitlement record linking a user to a book (manual/admin or future gateway)."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PAID = 'paid', 'Paid'
        REFUNDED = 'refunded', 'Refunded'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='purchases',
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.PROTECT,
        related_name='purchases',
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'book'],
                name='unique_user_book_purchase',
            ),
        ]

    def __str__(self):
        return f'{self.user_id}:{self.book_id} {self.status}'


class GenerationJob(models.Model):
    """Durable queue row for PDF/TTS generation (processed by management command)."""

    class JobType(models.TextChoices):
        PDF = 'pdf', 'PDF'
        AUDIO = 'audio', 'Audio'
        ALL = 'all', 'PDF and audio'

    class Status(models.TextChoices):
        QUEUED = 'queued', 'Queued'
        RUNNING = 'running', 'Running'
        DONE = 'done', 'Done'
        FAILED = 'failed', 'Failed'

    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name='generation_jobs',
    )
    job_type = models.CharField(max_length=16, choices=JobType.choices)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.QUEUED,
        db_index=True,
    )
    force = models.BooleanField(
        default=False,
        help_text='Force regenerate even when hashes match.',
    )
    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=3)
    locked_at = models.DateTimeField(blank=True, null=True)
    locked_by = models.CharField(max_length=64, blank=True, default='')
    error_message = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f'Job {self.pk} book={self.book_id} {self.job_type} {self.status}'
