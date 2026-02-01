from asgiref.sync import sync_to_async
from django.http import StreamingHttpResponse

class StreamingContentFixMiddleware:
    """Middleware to ensure StreamingHttpResponse has an async iterator when running under ASGI.

    If a view returns a StreamingHttpResponse with a synchronous iterator, Django raises a
    warning when serving it asynchronously. This middleware materializes the synchronous
    iterator into a list (in the current thread) and replaces the response.streaming_content
    with an async generator that yields the materialized chunks. This keeps behavior stable
    while avoiding the ASGI warning.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return self.process_response(request, response)

    def process_response(self, request, response):
        try:
            if isinstance(response, StreamingHttpResponse):
                content = getattr(response, 'streaming_content', None)
                if content is None:
                    return response

                # If it's a synchronous iterator (has __iter__ but no __aiter__), materialize it
                if hasattr(content, '__iter__') and not hasattr(content, '__aiter__'):
                    try:
                        # Materialize synchronously (keeps behavior identical)
                        chunks = list(content)

                        async def _async_gen():
                            for c in chunks:
                                yield c

                        response.streaming_content = _async_gen()
                    except Exception:
                        # If anything goes wrong, leave response unchanged
                        pass
        except Exception:
            # Don't allow middleware failures to break responses
            pass

        return response
