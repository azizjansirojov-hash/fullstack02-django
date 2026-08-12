"""Entitlement checks for paid book content (PDF, audio, immersive reader)."""

from .models import Book, Purchase


def paid_book_ids_for_user(user, book_ids) -> set[int]:
    """Return book IDs the user has a paid Purchase for (single query).

    Empty ``book_ids`` short-circuits without hitting the database.
    Does not include public-domain titles — callers must still treat
    ``rights_status == public_domain`` as entitled without a purchase.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return set()
    ids = [pk for pk in book_ids if pk is not None]
    if not ids:
        return set()
    return set(
        Purchase.objects.filter(
            user=user,
            book_id__in=ids,
            status=Purchase.Status.PAID,
        ).values_list('book_id', flat=True)
    )


def user_has_access_to_book(user, book: Book, *, paid_book_ids: set[int] | None = None) -> bool:
    """Entitlement check with optional preloaded paid-purchase ID set.

    When ``paid_book_ids`` is provided, no per-book Purchase query runs.
    """
    if book.rights_status == Book.RightsStatus.PUBLIC_DOMAIN:
        return True
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    if paid_book_ids is not None:
        return book.pk in paid_book_ids
    return Purchase.objects.filter(
        user=user,
        book=book,
        status=Purchase.Status.PAID,
    ).exists()


def user_can_access_book(user, book: Book) -> bool:
    """Return True when the user may stream/read full content for this book.

    Public-domain titles are free. All other rights statuses require a paid
    Purchase row for this user+book. Callers must already require authentication.
    """
    return user_has_access_to_book(user, book)
