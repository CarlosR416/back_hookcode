"""
Sub-domain tests: Ticket Cancellation & Status Lifecycle.
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.routers.models import Router
from apps.tickets.models import Ticket

User = get_user_model()


class TicketCancellationTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="ticketoperator",
            email="operator@example.com",
            password="operatorpass123",
        )
        cls.router = Router.objects.create(
            name="Tickets Router",
            host="192.168.88.1",
            port=443,
            api_username="admin",
            api_password="password",
        )

    def setUp(self):
        self.client.force_authenticate(user=self.user)

    def test_cancel_pending_ticket_success(self):
        """Cancelling a PENDING ticket marks its status as CANCELLED."""
        ticket = Ticket.objects.create(
            router=self.router,
            profile_name="default",
            duration_minutes=60,
            status=Ticket.Status.PENDING,
        )
        cancel_url = reverse("tickets:tickets-cancel", kwargs={"pk": ticket.pk})
        response = self.client.post(cancel_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, Ticket.Status.CANCELLED)

    def test_cannot_cancel_already_active_ticket(self):
        """Cannot cancel a ticket that is already ACTIVE."""
        ticket = Ticket.objects.create(
            router=self.router,
            profile_name="default",
            duration_minutes=60,
            status=Ticket.Status.ACTIVE,
        )
        cancel_url = reverse("tickets:tickets-cancel", kwargs={"pk": ticket.pk})
        response = self.client.post(cancel_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data.get("error", {}).get("code"), "invalid_status")
