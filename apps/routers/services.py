"""
Services for the routers application.

Handles dynamic, collision-free provisioning of router credentials,
sequential ports, and user identifiers (e.g., U10001).
"""

import secrets
import string

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .models import Router


def get_next_router_identifier(min_val: int = 10001, max_val: int = 15000) -> int:
    """
    Find the next available sequential integer in [min_val, max_val].

    Takes into account both existing Router ports and Router api_usernames matching 'U<number>'.
    Returns the lowest available integer >= min_val.
    Raises ValidationError if the range is exhausted.
    """
    allocated_ports = set(
        Router.objects.filter(port__gte=min_val, port__lte=max_val).values_list("port", flat=True)
    )

    allocated_users = set()
    username_list = Router.objects.filter(api_username__startswith="U").values_list(
        "api_username", flat=True
    )
    for uname in username_list:
        num_part = uname[1:]
        if num_part.isdigit():
            num = int(num_part)
            if min_val <= num <= max_val:
                allocated_users.add(num)

    used_indices = allocated_ports | allocated_users

    for candidate in range(min_val, max_val + 1):
        if candidate not in used_indices:
            return candidate

    raise ValidationError(
        _("No available router identifiers left in the configured range (%(min)d-%(max)d).")
        % {"min": min_val, "max": max_val}
    )


def generate_unique_router_password(length: int = 24, max_attempts: int = 100) -> str:
    """
    Generate a cryptographically secure, alphanumeric random password
    verified not to clash with any existing Router api_password.
    """
    alphabet = string.ascii_letters + string.digits
    for _ in range(max_attempts):
        candidate = "".join(secrets.choice(alphabet) for _ in range(length))
        if not Router.objects.filter(api_password=candidate).exists():
            return candidate

    raise ValidationError(_("Unable to generate a unique router password."))


def provision_router_defaults() -> dict:
    """
    Generate automatic default configuration and credentials for a new Router.
    """
    identifier = get_next_router_identifier()
    password = generate_unique_router_password()

    return {
        "host": "0.0.0.0",
        "port": identifier,
        "api_username": f"U{identifier}",
        "api_password": password,
        "is_active": True,
        "routeros_version": None,
    }
