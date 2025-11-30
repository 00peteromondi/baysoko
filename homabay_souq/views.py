from django.shortcuts import render

def custom_error_500(request):
    """Custom handler for server errors (500)"""
    response = render(request, '500.html', status=500)
    return response
