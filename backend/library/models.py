"""Book catalog models with Uzbek content translations."""

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
        help_text='Optional PDF file used by PDF reading mode and downloads.',
    )
    audio_file = models.FileField(
        upload_to='books/audio/',
        blank=True,
        null=True,
        help_text='Optional narration audio file for listen mode.',
    )
    author_name = models.CharField(max_length=200)
    category = models.CharField(
        max_length=32,
        choices=Category.choices,
        default=Category.OTHER,
        db_index=True,
        help_text='Keeps each title on its own shelf direction.',
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
