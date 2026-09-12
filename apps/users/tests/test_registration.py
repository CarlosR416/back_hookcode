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
        """Registering with simplified valid payload creates a user and returns 201."""
        payload = {
            "email": "newuser@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "password": "Password123!",
            "password_confirm": "Password123!",
        }
        response = self.client.post(self.register_url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email="newuser@example.com").exists())
        user = User.objects.get(email="newuser@example.com")
        self.assertEqual(user.first_name, "John")
        self.assertEqual(user.last_name, "Doe")
        self.assertEqual(user.username, "newuser@example.com")
        self.assertEqual(response.data["data"]["email"], "newuser@example.com")
        self.assertEqual(response.data["data"]["first_name"], "John")
        self.assertEqual(response.data["data"]["last_name"], "Doe")

    def test_registration_password_mismatch(self):
        """Fails when password and password_confirm do not match."""
        payload = {
            "email": "newuser@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "password": "Password123!",
            "password_confirm": "DifferentPassword123!",
        }
        response = self.client.post(self.register_url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("password_confirm", response.data["error"])

    def test_registration_missing_required_fields(self):
        """Fails when mandatory fields (first_name, last_name, email, password) are omitted."""
        response = self.client.post(self.register_url, data={}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data["error"])
        self.assertIn("first_name", response.data["error"])
        self.assertIn("last_name", response.data["error"])
        self.assertIn("password", response.data["error"])

    def test_registration_duplicate_email(self):
        """Fails when an email is already registered and verified."""
        User.objects.create_user(
            username="existing@example.com",
            email="existing@example.com",
            password="Password123!",
            is_email_verified=True,
        )
        payload = {
            "email": "existing@example.com",
            "first_name": "Jane",
            "last_name": "Smith",
            "password": "Password123!",
            "password_confirm": "Password123!",
        }
        response = self.client.post(self.register_url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("email", response.data["error"])

    def test_registration_unverified_email_replaces_info_and_succeeds(self):
        """When an email was registered but never verified, re-registering replaces info and succeeds with 201."""
        User.objects.create_user(
            username="unverified@example.com",
            email="unverified@example.com",
            first_name="OldName",
            last_name="OldLastName",
            password="OldPassword123!",
            is_active=False,
            is_email_verified=False,
        )
        payload = {
            "email": "unverified@example.com",
            "first_name": "NewName",
            "last_name": "NewLastName",
            "password": "NewPassword123!",
            "password_confirm": "NewPassword123!",
        }
        response = self.client.post(self.register_url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(email="unverified@example.com")
        self.assertEqual(user.first_name, "NewName")
        self.assertEqual(user.last_name, "NewLastName")
        self.assertTrue(user.check_password("NewPassword123!"))
        self.assertFalse(user.is_active)
        self.assertFalse(user.is_email_verified)
