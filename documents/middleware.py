from django.conf import settings
from django.shortcuts import render


class MaintenanceModeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.DOCFLOW_MAINTENANCE_MODE and not self._is_asset_request(request.path):
            response = render(request, "maintenance.html", status=503)
            response["Retry-After"] = str(settings.DOCFLOW_MAINTENANCE_RETRY_AFTER)
            return response
        return self.get_response(request)

    @staticmethod
    def _is_asset_request(path):
        static_prefix = f"/{settings.STATIC_URL.lstrip('/')}"
        media_prefix = f"/{settings.MEDIA_URL.lstrip('/')}"
        return path.startswith((static_prefix, media_prefix))
