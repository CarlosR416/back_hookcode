"""
Sub-domain tests: User Registration.
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


class UserRegistrationTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.register_url = reverse("auth:users-register")

    def test_registration_success(self):
        """Registering with valid payload creates a user and returns 201."""
        payload = {
            "email": "newuser@example.com",
            "username": "newuser",
            "first_name": "New",
            "last_name": "User",
            "password": "Password123!",
            "password_confirm": "Password123!",
        }
        response = self.client.post(self.register_url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email="newuser@example.com").exists())

    def test_registration_password_mismatch(self):
        """Fails when password and password_confirm do not match."""
        payload = {
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "Password123!",
            "password_confirm": "DifferentPassword123!",
        }
        response = self.client.post(self.register_url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("password_confirm", response.data["error"])

    def test_registration_missing_required_fields(self):
        """Fails when mandatory fields are omitted."""
        response = self.client.post(self.register_url, data={"username": "onlyuser"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data["error"])
        self.assertIn("password", response.data["error"])
