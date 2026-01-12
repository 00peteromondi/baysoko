# storefront/decorators.py
from functools import wraps
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from .models import Store


def store_owner_required(permission=None):
    """
    Decorator factory to ensure the requesting user owns the store.

    Can be used as either:
      @store_owner_required
    or
      @store_owner_required('inventory')
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # Get store slug from kwargs
            store_slug = kwargs.get('slug') or kwargs.get('store_slug')

            if not store_slug:
                # If no store slug in URL, user must own at least one store
                if not Store.objects.filter(owner=getattr(request, 'user', None)).exists():
                    raise PermissionDenied("You don't own any stores.")
                return view_func(request, *args, **kwargs)

            # Get the store
            store = get_object_or_404(Store, slug=store_slug)

            # Check if user owns the store or is staff
            user = getattr(request, 'user', None)
            if not user or (store.owner != user and not getattr(user, 'is_staff', False)):
                raise PermissionDenied("You don't have permission to access this store.")

            return view_func(request, *args, **kwargs)

        return _wrapped_view

    # Support being used without parentheses
    if callable(permission):
        return decorator(permission)

    return decorator


def staff_required(permission=None):
    """
    Decorator factory to require a staff role/permission for a view.

    Usage:
      @staff_required('inventory')
    or
      @staff_required
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            user = getattr(request, 'user', None)
            if not user or not user.is_authenticated:
                raise PermissionDenied("Authentication required.")

            # Strict policy: only the store creator (owner) may satisfy staff_required for store-scoped views.
            store_slug = kwargs.get('slug') or kwargs.get('store_slug')
            if not store_slug:
                try:
                    resolver = getattr(request, 'resolver_match', None)
                    if resolver:
                        store_slug = resolver.kwargs.get('slug') or resolver.kwargs.get('store_slug')
                except Exception:
                    store_slug = None

            if not store_slug:
                # No store context -> deny access
                raise PermissionDenied("Staff privileges required.")

            try:
                from .models import Store
                # Simple existence check avoids object identity issues
                if Store.objects.filter(slug=store_slug, owner_id=getattr(user, 'id', None)).exists():
                    return view_func(request, *args, **kwargs)
            except Exception:
                # If Store model unavailable, deny for safety
                raise PermissionDenied("Staff privileges required.")

            raise PermissionDenied("Staff privileges required.")

        return _wrapped_view

    if callable(permission):
        return decorator(permission)

    return decorator