from functools import wraps
from django.contrib.auth.decorators import user_passes_test
from django.http import HttpResponseForbidden


def delivery_person_required(view_func):
    """Decorator to ensure the user has a `delivery_person` related object."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return user_passes_test(lambda u: False)(view_func)(request, *args, **kwargs)
        if hasattr(request.user, 'delivery_person'):
            return view_func(request, *args, **kwargs)
        return HttpResponseForbidden('Delivery person access required')

    return _wrapped


def admin_required(view_func):
    """Decorator to ensure the user is staff or superuser."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return user_passes_test(lambda u: False)(view_func)(request, *args, **kwargs)
        if request.user.is_staff or request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        return HttpResponseForbidden('Admin access required')

    return _wrapped


def seller_or_delivery_or_admin_required(view_func):
    """Decorator to ensure the user is a store owner (seller), delivery person, or admin."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return user_passes_test(lambda u: False)(view_func)(request, *args, **kwargs)
        # Admins allowed
        if request.user.is_staff or request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        # Delivery personnel allowed
        if hasattr(request.user, 'delivery_person'):
            return view_func(request, *args, **kwargs)
        # Store owners allowed
        try:
            from storefront.models import Store
            if Store.objects.filter(owner=request.user).exists():
                return view_func(request, *args, **kwargs)
        except Exception:
            pass

        return HttpResponseForbidden('Access to delivery system is restricted to sellers and delivery personnel')

    return _wrapped
