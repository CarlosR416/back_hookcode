"""
Views for the tickets application.
"""

from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from core.mixins import StandardResponseMixin
from core.responses import created_response, error_response, success_response

from .models import Ticket
from .serializers import TicketActivateSerializer, TicketBulkGenerateSerializer, TicketSerializer
from .services import activate_ticket, generate_tickets


class TicketViewSet(StandardResponseMixin, ModelViewSet):
    """
    Ticket management endpoints.

    list:       GET  /api/tickets/
    retrieve:   GET  /api/tickets/{id}/
    destroy:    DELETE /api/tickets/{id}/
    generate:   POST /api/tickets/generate/
    activate:   POST /api/tickets/{id}/activate/
    cancel:     POST /api/tickets/{id}/cancel/
    """

    queryset = Ticket.objects.select_related("router").all()
    serializer_class = TicketSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "delete", "head", "options"]
    filterset_fields = ["router", "status", "profile_name"]

    # ── Bulk generation ────────────────────────────────────────────────────────

    @action(detail=False, methods=["post"], url_path="generate")
    def generate(self, request: Request) -> Response:
        """
        Generate a batch of ticket codes (no MikroTik interaction).

        Body:
            router (int):           Router ID
            profile_name (str):     MikroTik profile name
            duration_minutes (int): Session duration in minutes
            quantity (int):         Number of tickets (1–500)
            comment (str):          Optional comment
        """
        serializer = TicketBulkGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        tickets = generate_tickets(
            router=data["router"],
            profile_name=data["profile_name"],
            duration_minutes=data["duration_minutes"],
            quantity=data["quantity"],
            comment=data.get("comment", ""),
        )
        return created_response(TicketSerializer(tickets, many=True).data)

    # ── Per-ticket actions ─────────────────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request: Request, pk: int | None = None) -> Response:
        """
        Activate a PENDING ticket by creating a hotspot user on the router.

        Optional body:
            username (str): Override the auto-generated hotspot username.
        """
        ticket = self.get_object()
        serializer = TicketActivateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            ticket = activate_ticket(
                ticket=ticket,
                username=serializer.validated_data.get("username") or None,
            )
        except ValueError as exc:
            return error_response(str(exc), code="invalid_status")

        return success_response(TicketSerializer(ticket).data)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request: Request, pk: int | None = None) -> Response:
        """Cancel a PENDING ticket (marks it as CANCELLED, no router interaction)."""
        ticket = self.get_object()

        if ticket.status != Ticket.Status.PENDING:
            return error_response(
                _("Only PENDING tickets can be cancelled. Current status: %(status)s")
                % {"status": ticket.status},
                code="invalid_status",
            )

        ticket.status = Ticket.Status.CANCELLED
        ticket.save(update_fields=["status"])
        return success_response(TicketSerializer(ticket).data)
