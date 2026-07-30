"""Report rights_status distribution and likely misclassified classics (read-only)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.db.models import Count  # noqa: E402

from library.models import Book  # noqa: E402
from library.management.commands.flag_public_domain_classics import (  # noqa: E402
    PUBLIC_DOMAIN_AUTHOR_FRAGMENTS,
    PUBLIC_DOMAIN_TITLE_FRAGMENTS,
)


def main():
    print('=== rights_status distribution ===')
    for row in Book.objects.values('rights_status').annotate(n=Count('id')).order_by(
        'rights_status'
    ):
        print(row)
    print('=== total ===', Book.objects.count())
    print()
    print('=== all books ===')
    for b in Book.objects.prefetch_related('translations').order_by('pk'):
        title = (
            b.translations.filter(language='uz').values_list('title', flat=True).first() or ''
        )
        print(f'{b.pk}\t{b.slug}\t{b.author_name!r}\t{title!r}\t{b.rights_status}')
    print()
    print('=== heuristic mismatches (not public_domain but matches classic fragments) ===')
    mismatches = []
    for b in Book.objects.prefetch_related('translations').exclude(
        rights_status=Book.RightsStatus.PUBLIC_DOMAIN
    ):
        author_lower = (b.author_name or '').lower()
        titles = [t.title.lower() for t in b.translations.all() if t.title]
        matched = False
        reason = ''
        for frag in PUBLIC_DOMAIN_AUTHOR_FRAGMENTS:
            if frag in author_lower:
                matched = True
                reason = f'author contains {frag!r}'
                break
        if not matched:
            for frag in PUBLIC_DOMAIN_TITLE_FRAGMENTS:
                for title in titles:
                    if frag in title:
                        matched = True
                        reason = f'title contains {frag!r}'
                        break
                if matched:
                    break
        if matched:
            mismatches.append((b, reason))
            print(
                f'PROPOSE public_domain: pk={b.pk} slug={b.slug!r} '
                f'current={b.rights_status} reason={reason}'
            )
    if not mismatches:
        print('None found.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
