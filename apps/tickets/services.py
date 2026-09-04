"""
Tickets service — business logic for generating and activating tickets.

Kept outside the views so it can be reused from management commands,
Celery tasks, or other apps without importing HTTP-layer constructs.
"""

import logging
from datetime import datetime, timezone

from services.mikrotik.client import MikroTikClient
from services.mikrotik.hotspot import HotspotService

from .models import Ticket

logger = logging.getLogger(__name__)


def generate_tickets(
    router,
    profile_name: str,
    duration_minutes: int,
    quantity: int,
    comment: str = "",
) -> list[Ticket]:
    """
    Create *quantity* Ticket objects in the database with PENDING status.

    No MikroTik interaction happens here. Tickets are activated on demand
    by the customer or an operator.

    Args:
        router:           Router model instance.
        profile_name:     MikroTik hotspot profile to assign on activation.
        duration_minutes: Session duration in minutes.
        quantity:         Number of tickets to generate.
        comment:          Optional comment attached to each ticket.

    Returns:
        List of created Ticket instances.
    """
    tickets = [
        Ticket(
            router=router,
            profile_name=profile_name,
            duration_minutes=duration_minutes,
            comment=comment,
        )
        for _ in range(quantity)
    ]
    return Ticket.objects.bulk_create(tickets)


def activate_ticket(ticket: Ticket, username: str | None = None) -> Ticket:
    """
    Activate a PENDING ticket by creating a hotspot user on the router.

    Args:
        ticket:   A Ticket instance in PENDING status.
        username: Optional override for the hotspot username.
                  Defaults to the ticket code (first 12 chars).

    Returns:
        Updated Ticket instance with status=ACTIVE.

    Raises:
        ValueError: If the ticket is not in PENDING status.
        MikroTikConnectionError / MikroTikAPIError: On router communication failure.
    """
    if ticket.status != Ticket.Status.PENDING:
        raise ValueError(
            f"Ticket {ticket.code} cannot be activated — current status: {ticket.status}"
        )

    # Derive username from ticket code if not provided
    hotspot_username = username or str(ticket.code).replace("-", "")[:12]

    # Convert duration to RouterOS time format (minutes → "Xm")
    limit_uptime = f"{ticket.duration_minutes}m"

    client = MikroTikClient(
        host=ticket.router.host,
        username=ticket.router.api_username,
        password=ticket.router.api_password,
        port=ticket.router.port,
        ssl_verify=ticket.router.ssl_verify,
    )
    svc = HotspotService(client)
    result = svc.create_user(
        name=hotspot_username,
        password=str(ticket.code),  # UUID as password; change as needed
        profile=ticket.profile_name,
        limit_uptime=limit_uptime,
        comment=f"ticket:{ticket.pk}",
    )

    ticket.mk_user_id = result.get(".id", "")
    ticket.status = Ticket.Status.ACTIVE
    ticket.activated_at = datetime.now(tz=timezone.utc)
    ticket.save(update_fields=["mk_user_id", "status", "activated_at"])

    logger.info("Ticket %s activated as hotspot user '%s'.", ticket.code, hotspot_username)
    return ticket
