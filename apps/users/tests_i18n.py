"""
Tests for GNU gettext i18n and Accept-Language header handling.
"""

from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.routers.models import Router, UserRouter
from apps.tickets.models import Ticket

User = get_user_model()


class InternationalizationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password="oldpassword123",
        )
        self.admin = User.objects.create_superuser(
            username="adminuser",
            email="admin@example.com",
            password="adminpassword123",
        )
        self.router = Router.objects.create(
            name="Test Router",
            host="192.168.88.1",
            port=443,
            api_username="admin",
            api_password="password",
        )
        self.register_url = reverse("auth:users-register")
        self.change_password_url = reverse("auth:users-change-password")
        self.sessions_url = reverse("hotspot:hotspot-users-sessions")
        self.memberships_url = reverse("routers:router-memberships-list")

    def test_register_password_mismatch_in_spanish(self):
        """When Accept-Language is 'es', validation messages should be in Spanish."""
        payload = {
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "Password123!",
            "password_confirm": "MismatchPassword123!",
        }
        response = self.client.post(
            self.register_url,
            data=payload,
            format="json",
            HTTP_ACCEPT_LANGUAGE="es",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.headers.get("Content-Language"), "es")
        self.assertIn("error", response.data)
        self.assertIn("password_confirm", response.data["error"])
        self.assertIn("Las contraseñas no coinciden.", response.data["error"]["password_confirm"])

    def test_register_password_mismatch_in_english(self):
        """When Accept-Language is 'en', validation messages should be in English."""
        payload = {
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "Password123!",
            "password_confirm": "MismatchPassword123!",
        }
        response = self.client.post(
            self.register_url,
            data=payload,
            format="json",
            HTTP_ACCEPT_LANGUAGE="en",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.headers.get("Content-Language"), "en")
        self.assertIn("error", response.data)
        self.assertIn("password_confirm", response.data["error"])
        self.assertIn("Passwords do not match.", response.data["error"]["password_confirm"])

    def test_change_password_wrong_old_password_in_spanish(self):
        """Custom endpoint error messages should be localized to Spanish."""
        self.client.force_authenticate(user=self.user)
        payload = {
            "old_password": "WrongPassword123!",
            "new_password": "NewSecretPassword123!",
            "new_password_confirm": "NewSecretPassword123!",
        }
        response = self.client.post(
            self.change_password_url,
            data=payload,
            format="json",
            HTTP_ACCEPT_LANGUAGE="es",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.headers.get("Content-Language"), "es")
        self.assertEqual(
            response.data.get("error", {}).get("detail"),
            "La contraseña anterior es incorrecta.",
        )

    def test_change_password_success_in_spanish(self):
        """Custom endpoint success messages should be localized to Spanish."""
        self.client.force_authenticate(user=self.user)
        payload = {
            "old_password": "oldpassword123",
            "new_password": "NewSecretPassword123!",
            "new_password_confirm": "NewSecretPassword123!",
        }
        response = self.client.post(
            self.change_password_url,
            data=payload,
            format="json",
            HTTP_ACCEPT_LANGUAGE="es",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.headers.get("Content-Language"), "es")
        self.assertEqual(
            response.data.get("data", {}).get("detail"),
            "Contraseña actualizada exitosamente.",
        )

    def test_change_password_success_in_english(self):
        """Custom endpoint success messages should be in English by default or when requested."""
        self.client.force_authenticate(user=self.user)
        payload = {
            "old_password": "oldpassword123",
            "new_password": "NewSecretPassword123!",
            "new_password_confirm": "NewSecretPassword123!",
        }
        response = self.client.post(
            self.change_password_url,
            data=payload,
            format="json",
            HTTP_ACCEPT_LANGUAGE="en",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.headers.get("Content-Language"), "en")
        self.assertEqual(
            response.data.get("data", {}).get("detail"),
            "Password updated successfully.",
        )

    def test_drf_built_in_validation_translated_to_spanish(self):
        """DRF built-in validation messages (e.g. required field) should also be localized."""
        payload = {
            "username": "incompleteuser",
        }
        response = self.client.post(
            self.register_url,
            data=payload,
            format="json",
            HTTP_ACCEPT_LANGUAGE="es",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.headers.get("Content-Language"), "es")
        self.assertIn("error", response.data)
        self.assertIn("email", response.data["error"])
        self.assertIn("Este campo es requerido.", response.data["error"]["email"])

    def test_hotspot_missing_param_in_spanish(self):
        """Query parameter validation error should be translated to Spanish."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.sessions_url, HTTP_ACCEPT_LANGUAGE="es")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.headers.get("Content-Language"), "es")
        self.assertEqual(
            response.data.get("error", {}).get("detail"),
            "El parámetro de consulta 'router' es obligatorio.",
        )

    def test_hotspot_missing_param_in_english(self):
        """Query parameter validation error should be in English."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.sessions_url, HTTP_ACCEPT_LANGUAGE="en")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.headers.get("Content-Language"), "en")
        self.assertEqual(
            response.data.get("error", {}).get("detail"),
            "'router' query param is required.",
        )

    def test_ticket_cancel_non_pending_in_spanish(self):
        """Ticket cancel validation message should be in Spanish."""
        self.client.force_authenticate(user=self.user)
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
        self.client.force_authenticate(user=self.user)
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

    def test_duplicate_membership_validation_in_spanish(self):
        """Serializer unique validation message should be in Spanish."""
        self.client.force_authenticate(user=self.admin)
        UserRouter.objects.create(
            user=self.admin,
            router=self.router,
            role=UserRouter.RouterRole.OWNER,
        )
        payload = {
            "router": self.router.pk,
            "role": UserRouter.RouterRole.VIEWER,
        }
        response = self.client.post(
            self.memberships_url,
            data=payload,
            format="json",
            HTTP_ACCEPT_LANGUAGE="es",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.headers.get("Content-Language"), "es")
        self.assertIn(
            "Este usuario ya tiene un rol asignado para el router seleccionado.",
            str(response.data["error"]),
        )

    @patch("apps.users.firebase.verify_google_token")
    def test_google_login_missing_email_in_spanish(self, mock_verify):
        """Google login missing email message should be in Spanish."""
        mock_verify.return_value = {"uid": "google-user-123"}
        url = reverse("auth:users-google")
        response = self.client.post(
            url,
            data={"firebase_token": "valid-token-no-email"},
            format="json",
            HTTP_ACCEPT_LANGUAGE="es",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.headers.get("Content-Language"), "es")
        self.assertEqual(
            response.data.get("error", {}).get("detail"),
            "El correo electrónico no está presente en el token de Google.",
        )

    @patch("apps.users.firebase.verify_google_token")
    def test_google_login_missing_email_in_english(self, mock_verify):
        """Google login missing email message should be in English."""
        mock_verify.return_value = {"uid": "google-user-123"}
        url = reverse("auth:users-google")
        response = self.client.post(
            url,
            data={"firebase_token": "valid-token-no-email"},
            format="json",
            HTTP_ACCEPT_LANGUAGE="en",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.headers.get("Content-Language"), "en")
        self.assertEqual(
            response.data.get("error", {}).get("detail"),
            "Email is missing from the Google token.",
        )

