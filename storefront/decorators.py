# storefront/decorators.py
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from .models import Store

def store_owner_required(view_func):
    """
    Decorator to ensure the requesting user owns the store.
    """
    def _wrapped_view(request, *args, **kwargs):
        # Get store slug from kwargs
        store_slug = kwargs.get('slug') or kwargs.get('store_slug')
        
        if not store_slug:
            # If no store slug in URL, user must own at least one store
            if not Store.objects.filter(owner=request.user).exists():
                raise PermissionDenied("You don't own any stores.")
            return view_func(request, *args, **kwargs)
        
        # Get the store
        store = get_object_or_404(Store, slug=store_slug)
        
        # Check if user owns the store or is staff
        if store.owner != request.user and not request.user.is_staff:
            raise PermissionDenied("You don't have permission to access this store.")
        
        return view_func(request, *args, **kwargs)
    
    return _wrapped_view