"""
Sub-domain tests: Ticket Batch Generation.
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.routers.models import Router
from apps.tickets.models import Ticket

User = get_user_model()


class TicketGenerationTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="ticketadmin",
            email="ticketadmin@example.com",
            password="password123",
        )
        cls.router = Router.objects.create(
            name="Tickets Router",
            host="192.168.88.1",
            port=443,
            api_username="admin",
            api_password="password",
        )
        cls.generate_url = reverse("tickets:tickets-generate")

    def setUp(self):
        self.client.force_authenticate(user=self.user)

    def test_bulk_generation_success(self):
        """Generates a batch of tickets with UUIDs in PENDING status."""
        payload = {
            "router": self.router.pk,
            "profile_name": "1hour_5M",
            "duration_minutes": 60,
            "quantity": 5,
            "comment": "Batch #100",
        }
        response = self.client.post(self.generate_url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data["data"]), 5)
        self.assertEqual(
            Ticket.objects.filter(router=self.router, status=Ticket.Status.PENDING).count(),
            5,
        )

    def test_bulk_generation_invalid_quantity(self):
        """Fails when quantity is out of bounds (less than 1)."""
        payload = {
            "router": self.router.pk,
            "profile_name": "1hour_5M",
            "duration_minutes": 60,
            "quantity": 0,
        }
        response = self.client.post(self.generate_url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
