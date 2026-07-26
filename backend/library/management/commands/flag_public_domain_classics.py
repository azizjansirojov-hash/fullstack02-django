"""Flag classic public-domain titles so they remain free after Purchase gating."""

from django.core.management.base import BaseCommand
from django.db.models import Q

from library.models import Book

# Known public-domain authors / titles commonly in this catalog (Uzbek editions
# of 19th-century classics). Match is case-insensitive substring on author or title.
PUBLIC_DOMAIN_AUTHOR_FRAGMENTS = (
    'dostoyevsk',
    'dostoevsk',
    'tolstoy',
    'tolstoi',
    'pushkin',
    'chekhov',
    'chexov',
    'gogol',
    'shakespeare',
    'dickens',
    'verne',
    'hugo',
    'balzac',
    'austen',
    'bronte',
    'twain',
    'homer',
)

PUBLIC_DOMAIN_TITLE_FRAGMENTS = (
    'jinoyat va jazo',
    'crime and punishment',
    'urush va tinchlik',
    'war and peace',
    'anna karenina',
    'idiot',
)


class Command(BaseCommand):
    help = (
        'Set rights_status=public_domain for known classic public-domain works. '
        'Does not change books that are already public_domain.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report matches without writing.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        author_q = Q()
        for frag in PUBLIC_DOMAIN_AUTHOR_FRAGMENTS:
            author_q |= Q(author_name__icontains=frag)
        title_q = Q()
        for frag in PUBLIC_DOMAIN_TITLE_FRAGMENTS:
            title_q |= Q(translations__title__icontains=frag)

        qs = (
            Book.objects.filter(author_q | title_q)
            .exclude(rights_status=Book.RightsStatus.PUBLIC_DOMAIN)
            .distinct()
        )
        count = 0
        for book in qs:
            count += 1
            self.stdout.write(
                f'{"Would flag" if dry_run else "Flagging"} '
                f'pk={book.pk} slug={book.slug!r} author={book.author_name!r} '
                f'{book.rights_status} -> public_domain'
            )
            if not dry_run:
                book.rights_status = Book.RightsStatus.PUBLIC_DOMAIN
                book.save(update_fields=['rights_status', 'updated_at'])

        if count == 0:
            self.stdout.write(self.style.SUCCESS('No books needed updating.'))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'{"Matched" if dry_run else "Updated"} {count} book(s).'
                )
            )
