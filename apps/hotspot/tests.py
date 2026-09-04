"""
Tests for the hotspot application, including session querying, template files, and i18n messages.
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import HotspotTemplate

User = get_user_model()


class HotspotDomainTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="hotspotadmin",
            email="hotspot@example.com",
            password="hotspotpass123",
        )
        self.client.force_authenticate(user=self.user)
        self.sessions_url = reverse("hotspot:hotspot-users-sessions")
        self.template = HotspotTemplate.objects.create(
            name="Default Template",
            created_by=self.user,
        )
        self.template_files_url = reverse("hotspot:hotspot-template-files-list")

    def test_hotspot_missing_param_in_spanish(self):
        """Query parameter validation error should be translated to Spanish."""
        response = self.client.get(self.sessions_url, HTTP_ACCEPT_LANGUAGE="es")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.headers.get("Content-Language"), "es")
        self.assertEqual(
            response.data.get("error", {}).get("detail"),
            "El parámetro de consulta 'router' es obligatorio.",
        )

    def test_hotspot_missing_param_in_english(self):
        """Query parameter validation error should be in English."""
        response = self.client.get(self.sessions_url, HTTP_ACCEPT_LANGUAGE="en")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.headers.get("Content-Language"), "en")
        self.assertEqual(
            response.data.get("error", {}).get("detail"),
            "'router' query param is required.",
        )

    def test_template_file_path_separator_validation_in_spanish(self):
        """Path separator rejection message should be in Spanish."""
        payload = {
            "template": self.template.pk,
            "filename": "../evil.html",
            "content": "<h1>Malicious</h1>",
        }
        response = self.client.post(
            self.template_files_url,
            data=payload,
            format="json",
            HTTP_ACCEPT_LANGUAGE="es",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.headers.get("Content-Language"), "es")
        self.assertIn("filename", response.data["error"])
        self.assertIn(
            "El nombre de archivo no debe contener separadores de ruta ('/' o '\\').",
            response.data["error"]["filename"],
        )

    def test_template_file_path_separator_validation_in_english(self):
        """Path separator rejection message should be in English."""
        payload = {
            "template": self.template.pk,
            "filename": "../evil.html",
            "content": "<h1>Malicious</h1>",
        }
        response = self.client.post(
            self.template_files_url,
            data=payload,
            format="json",
            HTTP_ACCEPT_LANGUAGE="en",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.headers.get("Content-Language"), "en")
        self.assertIn("filename", response.data["error"])
        self.assertIn(
            "Filename must not contain path separators ('/' or '\\').",
            response.data["error"]["filename"],
        )
