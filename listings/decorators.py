# listings/decorators.py
from django.http import JsonResponse
from functools import wraps
import json

def ajax_required(view_func):
    """
    Decorator to ensure the view is called via AJAX.
    Also handles JsonResponse properly to avoid decorator chain issues.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # If not AJAX, return regular response
            return view_func(request, *args, **kwargs)
        
        try:
            response = view_func(request, *args, **kwargs)
            
            # If the view returns a JsonResponse, we need to handle it specially
            if isinstance(response, JsonResponse):
                return response
            
            # If it's a dict, convert to JsonResponse
            if isinstance(response, dict):
                return JsonResponse(response)
            
            return response
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    return wrapper