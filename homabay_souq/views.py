from django.shortcuts import render

def custom_error_500(request):
    """Custom handler for server errors (500)"""
    response = render(request, '500.html', status=500)
    return response


def custom_error_403(request, exception=None):
    """Custom handler for permission errors (403)"""
    response = render(request, '403.html', status=403)
    return response
