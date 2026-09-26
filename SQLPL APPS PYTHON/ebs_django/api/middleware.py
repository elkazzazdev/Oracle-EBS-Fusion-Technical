"""Custom middleware: activity logging."""
from .utils import log_activity, client_ip

SKIP_PATHS = (
    "/static/", "/media/", "/admin/jsi18n/",
    "/favicon.ico", "/api/auth/me", "/api/notifications/",
    "/api/ebs/session/", "/api/ebs/sessions/", "/api/session/info/",
)


class ActivityLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            path = request.path
            if any(path.startswith(p) for p in SKIP_PATHS):
                return response
            if not path.startswith("/api/"):
                return response
            if request.method in ("GET", "HEAD", "OPTIONS"):
                return response
            if 200 <= response.status_code < 400:
                user = getattr(request, "user", None)
                username = "ANON"
                if user and user.is_authenticated:
                    username = user.username
                action = f"{request.method} {path}"
                log_activity(username, action, "", client_ip(request))
        except Exception:
            pass
        return response