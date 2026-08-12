"""Notification creation helpers for library domain events."""


def _book_title(book):
    translation = book.get_translation()
    return translation.title if translation else book.slug


def notify_audio_ready(book):
    """Notify users currently reading this book that audio is ready."""
    from .models import Notification, ReadingProgress

    users = (
        ReadingProgress.objects.filter(
            book=book,
            status=ReadingProgress.Status.READING,
        )
        .values_list('user_id', flat=True)
        .distinct()
    )
    title = _book_title(book)
    link = f'/library/{book.slug}/'
    Notification.objects.bulk_create(
        [
            Notification(
                user_id=user_id,
                book=book,
                type=Notification.Type.AUDIO_READY,
                message=f'"{title}" audio versiyasi tayyor.',
                link_url=link,
            )
            for user_id in users
        ]
    )


def notify_purchase_paid(purchase):
    """Notify the purchaser once when a purchase becomes paid."""
    from .models import Notification

    title = _book_title(purchase.book)
    Notification.objects.create(
        user=purchase.user,
        book=purchase.book,
        type=Notification.Type.PURCHASE_PAID,
        message=f'"{title}" xaridingiz tasdiqlandi.',
        link_url=f'/library/{purchase.book.slug}/',
    )


def notify_purchase_refunded(purchase):
    """Notify the purchaser when paid access is revoked after a gateway refund."""
    from .models import Notification

    title = _book_title(purchase.book)
    Notification.objects.create(
        user=purchase.user,
        book=purchase.book,
        type=Notification.Type.PURCHASE_REFUNDED,
        message=f'"{title}" xaridingiz bekor qilindi. Kirish yopildi.',
        link_url=f'/library/{purchase.book.slug}/',
    )
