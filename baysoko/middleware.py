from django.shortcuts import redirect
from django.conf import settings


class ClearCorruptedSessionMiddleware:
    """Middleware that clears the session cookie if a corrupted session error occurs.

    This catches exceptions that mention session corruption (logged by Django when
    session decoding fails) and removes the client's session cookie to avoid
    repeated errors. It then redirects back to the same path so the client can
    continue with a fresh session.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            response = self.get_response(request)
            return response
        except Exception as exc:
            msg = str(exc).lower()
            if 'session data corrupted' in msg or 'session corrupted' in msg:
                response = redirect(request.path)
                try:
                    response.delete_cookie(settings.SESSION_COOKIE_NAME)
                except Exception:
                    pass
                return response
            raise
