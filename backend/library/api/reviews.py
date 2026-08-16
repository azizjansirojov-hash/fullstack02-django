"""Book review list/create/update/delete API."""

from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from users.authentication import CSRFEnforcedAuthentication, JWTCookieAuthentication

from ..access import user_can_access_book
from ..models import Book, Review
from ..serializers import ReviewSerializer, ReviewWriteSerializer
from ._common import REVIEW_PAGE_SIZE

class ReviewAPIView(APIView):
    """List, create, update, or delete the review for a published book.

    GET  — public, returns all reviews + aggregate stats.
    POST — authenticated; creates a review (one per user per book).
    PUT  — authenticated; updates the caller's existing review.
    DELETE — authenticated; deletes the caller's existing review.
    """

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'review_write'

    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_authenticators(self):
        if self.request.method == 'GET':
            return [JWTCookieAuthentication()]
        return [
            CSRFEnforcedAuthentication(),
            JWTCookieAuthentication(),
        ]

    def _get_published_book(self, slug):
        return get_object_or_404(Book, slug=slug, is_published=True)

    def get_throttles(self):
        # Keep review browsing public/unthrottled; throttle only writes.
        if self.request.method == 'GET':
            return []
        return super().get_throttles()

    def get(self, request, slug):
        book = self._get_published_book(slug)
        reviews_qs = book.reviews.select_related('user').order_by('-created_at')
        agg = book.reviews.aggregate(avg=Avg('rating'), total=Count('id'))
        paginator = Paginator(reviews_qs, REVIEW_PAGE_SIZE)
        page = paginator.get_page(request.GET.get('page') or 1)
        payload = {
            'count': agg['total'],
            'average_rating': round(agg['avg'], 2) if agg['avg'] else None,
            'results': ReviewSerializer(page.object_list, many=True).data,
            'pagination': {
                'page': page.number,
                'num_pages': page.paginator.num_pages,
                'has_previous': page.has_previous(),
                'has_next': page.has_next(),
                'previous_page': (
                    page.previous_page_number() if page.has_previous() else None
                ),
                'next_page': page.next_page_number() if page.has_next() else None,
            },
        }
        if request.user and request.user.is_authenticated:
            mine = book.reviews.filter(user=request.user).select_related('user').first()
            payload['my_review'] = (
                ReviewSerializer(mine).data if mine else None
            )
        return Response(payload)

    def _require_access(self, request, book):
        if not user_can_access_book(request.user, book):
            return Response(
                {'detail': 'Purchase required to access this book.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return None

    def post(self, request, slug):
        book = self._get_published_book(slug)
        denied = self._require_access(request, book)
        if denied is not None:
            return denied
        if Review.objects.filter(user=request.user, book=book).exists():
            return Response(
                {'detail': 'You already have a review for this book. Use PUT to update it.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = ReviewWriteSerializer(data=request.data)
        if not serializer.is_valid():
            detail = next(iter(serializer.errors.values()))[0]
            if 'rating' in serializer.errors:
                detail = 'rating must be an integer between 1 and 5.'
            elif 'text' in serializer.errors:
                detail = 'text must not exceed 2000 characters.'
            return Response({'detail': detail}, status=status.HTTP_400_BAD_REQUEST)
        rating = serializer.validated_data['rating']
        text = serializer.validated_data.get('text', '')
        try:
            review = Review.objects.create(
                user=request.user, book=book, rating=rating, text=text
            )
        except IntegrityError:
            return Response(
                {'detail': 'You already have a review for this book. Use PUT to update it.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(ReviewSerializer(review).data, status=status.HTTP_201_CREATED)

    def put(self, request, slug):
        book = self._get_published_book(slug)
        denied = self._require_access(request, book)
        if denied is not None:
            return denied
        review = Review.objects.filter(user=request.user, book=book).first()
        if not review:
            return Response(
                {'detail': 'No review found. Use POST to create one.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = ReviewWriteSerializer(data=request.data)
        if not serializer.is_valid():
            detail = next(iter(serializer.errors.values()))[0]
            if 'rating' in serializer.errors:
                detail = 'rating must be an integer between 1 and 5.'
            elif 'text' in serializer.errors:
                detail = 'text must not exceed 2000 characters.'
            return Response({'detail': detail}, status=status.HTTP_400_BAD_REQUEST)
        review.rating = serializer.validated_data['rating']
        review.text = serializer.validated_data.get('text', '')
        review.save(update_fields=['rating', 'text', 'updated_at'])
        return Response(ReviewSerializer(review).data)

    def delete(self, request, slug):
        book = self._get_published_book(slug)
        denied = self._require_access(request, book)
        if denied is not None:
            return denied
        review = Review.objects.filter(user=request.user, book=book).first()
        if not review:
            return Response(
                {'detail': 'No review found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        review.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


