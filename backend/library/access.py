"""Entitlement checks for paid book content (PDF, audio, immersive reader)."""

from .models import Book, Purchase


def user_can_access_book(user, book: Book) -> bool:
    """Return True when the user may stream/read full content for this book.

    Public-domain titles are free. All other rights statuses require a paid
    Purchase row for this user+book. Callers must already require authentication.
    """
    if book.rights_status == Book.RightsStatus.PUBLIC_DOMAIN:
        return True
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    return Purchase.objects.filter(
        user=user,
        book=book,
        status=Purchase.Status.PAID,
    ).exists()
