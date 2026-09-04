"""
Sub-domain tests: Hotspot Active Sessions.
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class HotspotSessionsTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="hotspotoperator",
            email="hotspotoperator@example.com",
            password="password123",
        )
        cls.sessions_url = reverse("hotspot:hotspot-users-sessions")

    def setUp(self):
        self.client.force_authenticate(user=self.user)

    def test_sessions_requires_router_param(self):
        """Fails with 400 when ?router= query param is missing."""
        response = self.client.get(self.sessions_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data.get("error", {}).get("code"), "missing_param")
