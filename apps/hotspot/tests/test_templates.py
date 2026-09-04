"""
Sub-domain tests: Hotspot Captive Portal Templates & Files.
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.hotspot.models import HotspotTemplate, HotspotTemplateFile

User = get_user_model()


class HotspotTemplatesTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="templateadmin",
            email="templateadmin@example.com",
            password="password123",
        )
        cls.template = HotspotTemplate.objects.create(
            name="Corporate Hotspot Template",
            created_by=cls.user,
        )
        cls.template_files_url = reverse("hotspot:hotspot-template-files-list")

    def setUp(self):
        self.client.force_authenticate(user=self.user)

    def test_create_template_file_success(self):
        """Creates a valid template file associated with a template."""
        payload = {
            "template": self.template.pk,
            "filename": "login.html",
            "role": HotspotTemplateFile.FileRole.LOGIN,
            "content": "<html><body>Login</body></html>",
            "mime_type": "text/html",
        }
        response = self.client.post(self.template_files_url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            HotspotTemplateFile.objects.filter(
                template=self.template, filename="login.html"
            ).exists()
        )

    def test_reject_filename_with_path_traversal(self):
        """Rejects filenames containing path separators to prevent path traversal."""
        payload = {
            "template": self.template.pk,
            "filename": "../../etc/passwd",
            "role": HotspotTemplateFile.FileRole.OTHER,
            "content": "invalid",
        }
        response = self.client.post(self.template_files_url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("filename", response.data.get("error", {}))
