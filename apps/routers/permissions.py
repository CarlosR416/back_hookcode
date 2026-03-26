"""
Permission classes for the routers application.

Design (SOLID / ISP):
- Each class encodes EXACTLY one policy question.
- Views compose them freely without inheriting behaviour they don't need.
- Adding a new policy means adding a class; existing classes are untouched (OCP).
- All classes depend only on `request.user` and `UserRouter`; they are decoupled
  from the concrete User model (DIP).
"""

from rest_framework.permissions import BasePermission, IsAuthenticated

from .models import UserRouter


# ---------------------------------------------------------------------------
# Low-level helpers (not exposed as permission classes)
# ---------------------------------------------------------------------------


def _get_user_role(user, router_id) -> str | None:
    """Return the role the user holds for this router, or None."""
    try:
        return UserRouter.objects.get(user=user, router_id=router_id).role
    except UserRouter.DoesNotExist:
        return None


def _is_router_owner(user, router_id: int) -> bool:
    """Return True if the user is the OWNER of the given router."""
    return _get_user_role(user, router_id) == UserRouter.RouterRole.OWNER


def _has_router_access(user, router_id: int) -> bool:
    """Return True if the user has ANY role on the given router."""
    return UserRouter.objects.filter(user=user, router_id=router_id).exists()


# ---------------------------------------------------------------------------
# ISP-friendly permission classes
# ---------------------------------------------------------------------------


class IsRouterOwner(BasePermission):
    """
    Object-level permission: user must be the OWNER of the router.

    Use for write operations (create, update, delete, live actions).
    """

    message = "You must be the owner of this router to perform this action."

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj) -> bool:
        if request.user.is_staff:
            return True
        return _is_router_owner(request.user, obj.pk)


class IsRouterMember(BasePermission):
    """
    Object-level permission: user must have ANY role on the router (owner or viewer).

    Use for read-only operations (retrieve, ping, resource, interfaces).
    """

    message = "You do not have access to this router."

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj) -> bool:
        if request.user.is_staff:
            return True
        return _has_router_access(request.user, obj.pk)


class IsAdminOrReadOwner(BasePermission):
    """
    List-level permission composite:
    - Admin (is_staff) → sees everything.
    - Regular user → list is later filtered by queryset (see RouterViewSet).

    This class only guards the endpoint entrance; row-level filtering
    is the ViewSet's responsibility.
    """

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated)
