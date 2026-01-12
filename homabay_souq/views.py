from django.shortcuts import render

def custom_error_500(request):
    """Custom handler for server errors (500)"""
    response = render(request, '500.html', status=500)
    return response


def custom_error_403(request, exception=None):
    """Render 500 template for 403 responses so users see the same error page."""
    # Intentionally render the 500 template to match requested UX
    response = render(request, '500.html', status=403)
    return response
