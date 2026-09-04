"""
Tests for the tickets application, including lifecycle actions and i18n messages.
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.routers.models import Router
from .models import Ticket

User = get_user_model()


class TicketDomainTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ticketoperator",
            email="operator@example.com",
            password="operatorpass123",
        )
        self.router = Router.objects.create(
            name="Tickets Router",
            host="192.168.88.1",
            port=443,
            api_username="admin",
            api_password="password",
        )
        self.client.force_authenticate(user=self.user)

    def test_ticket_cancel_non_pending_in_spanish(self):
        """Ticket cancel validation message should be in Spanish."""
        ticket = Ticket.objects.create(
            router=self.router,
            profile_name="default",
            duration_minutes=60,
            status=Ticket.Status.ACTIVE,
        )
        cancel_url = reverse("tickets:tickets-cancel", kwargs={"pk": ticket.pk})
        response = self.client.post(cancel_url, HTTP_ACCEPT_LANGUAGE="es")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.headers.get("Content-Language"), "es")
        self.assertIn(
            "Solo los tickets PENDIENTES pueden ser cancelados. Estado actual: active",
            response.data.get("error", {}).get("detail"),
        )

    def test_ticket_cancel_non_pending_in_english(self):
        """Ticket cancel validation message should be in English."""
        ticket = Ticket.objects.create(
            router=self.router,
            profile_name="default",
            duration_minutes=60,
            status=Ticket.Status.ACTIVE,
        )
        cancel_url = reverse("tickets:tickets-cancel", kwargs={"pk": ticket.pk})
        response = self.client.post(cancel_url, HTTP_ACCEPT_LANGUAGE="en")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.headers.get("Content-Language"), "en")
        self.assertIn(
            "Only PENDING tickets can be cancelled. Current status: active",
            response.data.get("error", {}).get("detail"),
        )

    def test_ticket_cancel_pending_success(self):
        """Cancelling a PENDING ticket succeeds and updates status."""
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
