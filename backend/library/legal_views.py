"""Legal pages and rights-holder report form for the bookstore."""

from django.conf import settings
from django.core.mail import send_mail
from django.shortcuts import render
from django.views import View
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from users.authentication import CSRFEnforcedAuthentication


class TermsPageView(View):
    def get(self, request):
        return render(request, 'legal/terms.html')


class PrivacyPageView(View):
    def get(self, request):
        return render(request, 'legal/privacy.html')


class RightsReportPageView(View):
    def get(self, request):
        return render(
            request,
            'legal/rights_report.html',
            {
                'rights_email': getattr(settings, 'RIGHTS_CONTACT_EMAIL', '')
                or settings.DEFAULT_FROM_EMAIL,
            },
        )


class RightsReportAPIView(APIView):
    """Accept a rights-holder / DMCA-style report and email staff."""

    permission_classes = [AllowAny]
    authentication_classes = [CSRFEnforcedAuthentication]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'rights_report'

    def post(self, request):
        name = (request.data.get('name') or '').strip()[:200]
        email = (request.data.get('email') or '').strip()[:200]
        book_ref = (request.data.get('book_ref') or '').strip()[:300]
        message = (request.data.get('message') or '').strip()[:5000]
        if not email or not message:
            return Response(
                {'detail': 'Email and message are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        to_addr = (
            getattr(settings, 'RIGHTS_CONTACT_EMAIL', '') or settings.DEFAULT_FROM_EMAIL
        )
        body = (
            f'Rights report from {name or "(no name)"} <{email}>\n'
            f'Book / URL reference: {book_ref or "(none)"}\n\n'
            f'{message}\n'
        )
        send_mail(
            subject='[Libro.UZ] Rights / DMCA report',
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to_addr],
            fail_silently=False,
        )
        return Response({'detail': 'Report submitted. We will review it.'})
