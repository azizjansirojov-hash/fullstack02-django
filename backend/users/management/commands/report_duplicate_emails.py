"""Detect duplicate user emails (case-insensitive) before unique index migration."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count
from django.db.models.functions import Lower

User = get_user_model()


class Command(BaseCommand):
    help = (
        'Report users sharing the same email ignoring case. '
        'Exit code 1 when non-empty duplicate groups exist.'
    )

    def handle(self, *args, **options):
        duplicates = (
            User.objects.exclude(email='')
            .annotate(email_ci=Lower('email'))
            .values('email_ci')
            .annotate(n=Count('id'))
            .filter(n__gt=1)
            .order_by('email_ci')
        )

        found = False
        for row in duplicates:
            found = True
            email_ci = row['email_ci']
            users = User.objects.filter(email__iexact=email_ci).order_by('id')
            ids = ', '.join(f'{u.id}:{u.username}' for u in users)
            self.stdout.write(
                self.style.WARNING(
                    f'Duplicate email {email_ci!r} ({row["n"]} users): {ids}'
                )
            )

        if found:
            raise CommandError(
                'Duplicate emails found. Resolve them before applying '
                'the case-insensitive unique email constraint.'
            )

        self.stdout.write(self.style.SUCCESS('No duplicate emails found.'))
