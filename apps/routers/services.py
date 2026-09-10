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


def generate_router_radius_password(
    length: int = 24, exclude_password: str | None = None
) -> str:
    """
    Generate a cryptographically secure, alphanumeric random password for RADIUS,
    guaranteed to be different from the provided exclude_password.
    """
    alphabet = string.ascii_letters + string.digits
    while True:
        candidate = "".join(secrets.choice(alphabet) for _ in range(length))
        if candidate != exclude_password:
            return candidate


def sync_router_radius_user(
    router: Router,
    password: str | None = None,
) -> dict | None:
    """
    Provision a FreeRADIUS user for the router using an independent random password
    distinct from the router's API credentials, and assign client_id = router.port - 10000.
    """
    from apps.radius.services import RadiusService

    if not router.api_username:
        raise ValueError("Router must have an api_username to provision a RADIUS user.")

    if router.port is None:
        raise ValueError("Router must have a port to provision a RADIUS user.")

    client_id = router.port - 10000
    if client_id < 0:
        raise ValueError(
            f"Router client_id cannot be less than zero (port: {router.port}, client_id: {client_id})."
        )

    radius_password = password or generate_router_radius_password(
        exclude_password=router.api_password
    )

    result = RadiusService.add_user(
        username=router.api_username,
        password=radius_password,
        client_id=client_id,
    )
    result["password"] = radius_password
    return result


def delete_router_radius_user(router: Router) -> bool:
    """
    Remove the FreeRADIUS user matching the router's API username.
    """
    from apps.radius.services import RadiusService

    if not router.api_username:
        return False

    return RadiusService.delete_user(username=router.api_username)


def generate_router_vpn_provisioning_token(
    router: Router,
    request=None,
    expiration_minutes: int | None = None,
    filename: str = "vpn_setup.rsc",
) -> dict:
    """
    Generate a single-use provisioning token for configuring an automated IKEv2 VPN client on MikroTik.

    Dynamically binds to the first active VPN node, the seeded 'MikroTik IKEv2 VPN Client' template,
    and the FreeRADIUS credentials for the router's api_username.
    """
    from datetime import timedelta
    from django.conf import settings
    from django.urls import reverse
    from django.utils import timezone
    from apps.radius.models import RadCheck
    from apps.scripts.models import ScriptDownloadToken, ScriptTemplate
    from apps.vpn.models import VpnNode

    vpn_node = VpnNode.objects.filter(is_active=True).first()
    if not vpn_node:
        raise ValidationError(_("No active VPN node is currently available."))

    template = ScriptTemplate.objects.filter(name="MikroTik IKEv2 VPN Client").first()
    if not template:
        raise ValidationError(_("VPN script template 'MikroTik IKEv2 VPN Client' not found."))

    if not router.api_username:
        raise ValidationError(_("Router does not have an api_username configured."))

    radcheck = RadCheck.objects.filter(
        username=router.api_username,
        attribute="Cleartext-Password",
    ).first()

    if not radcheck:
        sync_result = sync_router_radius_user(router)
        radius_password = sync_result["password"]
    else:
        radius_password = radcheck.value

    radius_username = router.api_username

    vpn_server_internal_ip = vpn_node.internal_ip.split("/")[0] if vpn_node.internal_ip else ""
    if not vpn_server_internal_ip:
        raise ValidationError(_("Active VPN node does not have an internal IP configured."))

    cert_url = reverse("vpn:nodes-certificate", kwargs={"pk": vpn_node.pk})
    if request:
        cert_download_url = f"{request.build_absolute_uri(cert_url)}?raw=true"
    else:
        cert_download_url = f"{cert_url}?raw=true"

    exp_minutes = (
        expiration_minutes
        if expiration_minutes is not None
        else getattr(settings, "SCRIPT_TOKEN_EXPIRATION_MINUTES", 10)
    )
    token = secrets.token_urlsafe(32)
    expires_at = timezone.now() + timedelta(minutes=exp_minutes)

    token_record = ScriptDownloadToken.objects.create(
        router=router,
        template=template,
        variables_used={
            "cert_download_url": cert_download_url,
            "vpn_server_address": vpn_node.host,
            "radius_username": radius_username,
            "radius_password": radius_password,
            "vpn_server_internal_ip": vpn_server_internal_ip,
            "vpn_node_id": vpn_node.pk,
            "vpn_node_name": vpn_node.name,
            "router_name": router.name,
        },
        token=token,
        expires_at=expires_at,
        include_cleanup=True,
        filename=filename,
    )

    if request:
        download_url = request.build_absolute_uri(
            reverse("scripts:script-download", kwargs={"token": token})
        )
    else:
        download_url = reverse("scripts:script-download", kwargs={"token": token})

    routeros_cmd = (
        f'/tool fetch url="{download_url}" mode=https dst-path="{filename}"; '
        f':delay 1s; /import {filename}'
    )

    return {
        "token": token_record.token,
        "download_url": download_url,
        "routeros_command": routeros_cmd,
        "expires_at": token_record.expires_at,
    }


def get_router_vpn_connection_info(router: Router) -> dict:
    """
    Query FreeRADIUS accounting (radacct) to evaluate the router's VPN connection status.
    Returns a dictionary structured as:
      - status: 'NEVER_CONNECTED' | 'CONNECTED' | 'DISCONNECTED'
      - is_connected: bool
      - tunnel_ip: str | None
      - connected_at: datetime | None
      - last_seen: datetime | None
    """
    from apps.radius.models import RadAcct

    default_info = {
        "status": "NEVER_CONNECTED",
        "is_connected": False,
        "tunnel_ip": None,
        "connected_at": None,
        "last_seen": None,
    }

    if not router.api_username:
        return default_info

    try:
        # Check for active session first (acctstoptime IS NULL)
        active_session = (
            RadAcct.objects.filter(username=router.api_username, acctstoptime__isnull=True)
            .order_by("-acctstarttime")
            .first()
        )
        if active_session:
            return {
                "status": "CONNECTED",
                "is_connected": True,
                "tunnel_ip": active_session.framedipaddress,
                "connected_at": active_session.acctstarttime,
                "last_seen": None,
            }

        # Check for historical sessions
        last_session = (
            RadAcct.objects.filter(username=router.api_username)
            .order_by("-acctstoptime", "-acctstarttime")
            .first()
        )
        if last_session:
            return {
                "status": "DISCONNECTED",
                "is_connected": False,
                "tunnel_ip": last_session.framedipaddress,
                "connected_at": last_session.acctstarttime,
                "last_seen": last_session.acctstoptime,
            }

        return default_info
    except Exception:
        return default_info


def get_batch_routers_vpn_connection_info(routers: list[Router]) -> dict[int, dict]:
    """
    Batch query FreeRADIUS accounting (radacct) for multiple routers in a single SQL operation.
    Maps router.id -> vpn_connection_info dict.
    """
    from apps.radius.models import RadAcct

    default_info = {
        "status": "NEVER_CONNECTED",
        "is_connected": False,
        "tunnel_ip": None,
        "connected_at": None,
        "last_seen": None,
    }

    result = {r.id: dict(default_info) for r in routers}
    usernames = [r.api_username for r in routers if r.api_username]
    if not usernames:
        return result

    try:
        # 1. Active sessions
        active_records = RadAcct.objects.filter(
            username__in=usernames, acctstoptime__isnull=True
        )
        active_map: dict[str, dict] = {}
        for rec in active_records:
            active_map[rec.username] = {
                "status": "CONNECTED",
                "is_connected": True,
                "tunnel_ip": rec.framedipaddress,
                "connected_at": rec.acctstarttime,
                "last_seen": None,
            }

        # 2. Historical sessions for those without active sessions
        remaining_usernames = set(usernames) - set(active_map.keys())
        history_map: dict[str, dict] = {}
        if remaining_usernames:
            historical_records = (
                RadAcct.objects.filter(username__in=remaining_usernames)
                .order_by("username", "-acctstoptime", "-acctstarttime")
            )
            for rec in historical_records:
                if rec.username not in history_map:
                    history_map[rec.username] = {
                        "status": "DISCONNECTED",
                        "is_connected": False,
                        "tunnel_ip": rec.framedipaddress,
                        "connected_at": rec.acctstarttime,
                        "last_seen": rec.acctstoptime,
                    }

        for router in routers:
            uname = router.api_username
            if uname in active_map:
                result[router.id] = active_map[uname]
            elif uname in history_map:
                result[router.id] = history_map[uname]

        return result
    except Exception:
        return result



