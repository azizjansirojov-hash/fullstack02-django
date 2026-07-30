"""Staff-only generation worker health endpoint."""

from django.http import JsonResponse
from django.views import View

from .auth_access import AuthRequiredMixin, ensure_request_user
from .generation_health import generation_health_payload


class GenerationHealthView(AuthRequiredMixin, View):
    """JSON health for PDF/TTS queue. Staff only (bookstore ops)."""

    def dispatch(self, request, *args, **kwargs):
        ensure_request_user(request)
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        if not request.user.is_staff:
            return JsonResponse({'detail': 'Staff only.'}, status=403)
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        payload = generation_health_payload()
        status_code = 503 if payload['worker_likely_down'] else 200
        return JsonResponse(payload, status=status_code)
