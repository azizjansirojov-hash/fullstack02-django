"""Report duplicate AudioChapter (book, order) rows before unique constraint."""

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count

from library.models import AudioChapter


class Command(BaseCommand):
    help = (
        'Report AudioChapter rows that share the same book + order. '
        'Exit code 1 when duplicates exist.'
    )

    def handle(self, *args, **options):
        duplicates = (
            AudioChapter.objects.values('book_id', 'order')
            .annotate(n=Count('id'))
            .filter(n__gt=1)
            .order_by('book_id', 'order')
        )
        found = False
        for row in duplicates:
            found = True
            ids = list(
                AudioChapter.objects.filter(
                    book_id=row['book_id'],
                    order=row['order'],
                )
                .order_by('id')
                .values_list('id', flat=True)
            )
            self.stdout.write(
                self.style.WARNING(
                    f'Duplicate book_id={row["book_id"]} order={row["order"]} '
                    f'({row["n"]} rows): ids={ids}'
                )
            )
        if found:
            raise CommandError(
                'Duplicate AudioChapter (book, order) rows found. '
                'Resolve them before applying the unique constraint.'
            )
        self.stdout.write(self.style.SUCCESS('No duplicate AudioChapter orders.'))
