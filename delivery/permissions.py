from rest_framework.permissions import BasePermission


class IsDeliveryPerson(BasePermission):
    """Allow access only to users with a related `delivery_person` object."""

    def has_permission(self, request, view):
        return bool(request.user and getattr(request.user, 'delivery_person', None))


class IsDeliveryOwner(BasePermission):
    """Allow access only if the user owns the delivery object (delivery_person.user)."""

    def has_object_permission(self, request, view, obj):
        try:
            return obj.delivery_person.user == request.user
        except Exception:
            return False
