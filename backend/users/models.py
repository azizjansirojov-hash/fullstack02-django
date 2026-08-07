"""User-facing preference models."""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

DEFAULT_DAILY_GOAL_MINUTES = 20
MIN_DAILY_GOAL_MINUTES = 5
MAX_DAILY_GOAL_MINUTES = 300


class UserPreferences(models.Model):
    """Per-user reading preferences (OneToOne to auth.User)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='preferences',
    )
    daily_goal_minutes = models.PositiveIntegerField(
        default=DEFAULT_DAILY_GOAL_MINUTES,
        validators=[
            MinValueValidator(MIN_DAILY_GOAL_MINUTES),
            MaxValueValidator(MAX_DAILY_GOAL_MINUTES),
        ],
        help_text='Daily reading goal in minutes (5–300).',
    )

    class Meta:
        verbose_name_plural = 'user preferences'

    def __str__(self):
        return f'{self.user_id} goal={self.daily_goal_minutes}m'
