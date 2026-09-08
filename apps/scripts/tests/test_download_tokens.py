"""
Sub-domain tests: Single-use (Burn-on-Read) Script Download Tokens.
"""

from datetime import timedelta
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.routers.models import Router, UserRouter
from apps.scripts.models import RouterScriptExecution, ScriptDownloadToken, ScriptTemplate

User = get_user_model()


class ScriptDownloadTokenTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            username="tokenowner",
            email="owner@example.com",
            password="password123",
        )
        cls.viewer = User.objects.create_user(
            username="tokenviewer",
            email="viewer@example.com",
            password="password123",
        )
        cls.unrelated = User.objects.create_user(
            username="unrelateduser",
            email="unrelated@example.com",
            password="password123",
        )
        cls.router = Router.objects.create(
            name="Bootstrap Router",
            host="192.168.88.1",
            port=443,
            api_username="admin",
            api_password="password",
        )
        UserRouter.objects.create(
            user=cls.owner,
            router=cls.router,
            role=UserRouter.RouterRole.OWNER,
        )
        UserRouter.objects.create(
            user=cls.viewer,
            router=cls.router,
            role=UserRouter.RouterRole.VIEWER,
        )

        cls.template = ScriptTemplate.objects.create(
            name="VPN Bootstrap",
            content="/interface wireguard add name=wg0 listen-port={{ wg_port }}\n"
                    "/interface wireguard peers add interface=wg0 public-key=\"{{ pubkey }}\"",
        )

        cls.router_token_url = reverse(
            "routers:routers-generate-bootstrap-token", kwargs={"pk": cls.router.pk}
        )

    def test_model_validity_and_burning(self):
        """Test token validity lifecycle and burn method."""
        token_record = ScriptDownloadToken.objects.create(
            router=self.router,
            template=self.template,
            variables_used={"wg_port": 13231, "pubkey": "testkey123"},
            token="test-token-validity",
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        self.assertTrue(token_record.is_valid())
        self.assertFalse(token_record.is_consumed)
        self.assertIsNone(token_record.consumed_at)

        # Test rendered_content with cleanup
        content = token_record.rendered_content
        self.assertIn("# WiFi Tickets - Automated RouterOS Provisioning Script", content)
        self.assertIn("listen-port=13231", content)
        self.assertIn('/file remove [find name="setup.rsc"]', content)

        # Burn token
        token_record.burn()
        self.assertTrue(token_record.is_consumed)
        self.assertIsNotNone(token_record.consumed_at)
        self.assertFalse(token_record.is_valid())

    def test_model_expired_token_is_invalid(self):
        """Test that an expired token reports is_valid() as False."""
        expired_token = ScriptDownloadToken.objects.create(
            router=self.router,
            token="test-expired-token",
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        self.assertFalse(expired_token.is_valid())

    def test_owner_can_generate_bootstrap_token(self):
        """Router owner can generate a bootstrap download token."""
        self.client.force_authenticate(user=self.owner)
        payload = {
            "template": self.template.pk,
            "variables": {"wg_port": 51820, "pubkey": "secretbase64key="},
            "expiration_minutes": 15,
            "filename": "wireguard.rsc",
            "include_cleanup": True,
        }
        response = self.client.post(self.router_token_url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        data = response.data["data"]
        self.assertIn("token", data)
        self.assertIn("download_url", data)
        self.assertIn("routeros_command", data)
        self.assertIn("expires_at", data)
        self.assertIn("/tool fetch", data["routeros_command"])
        self.assertIn('dst-path="wireguard.rsc"', data["routeros_command"])
        self.assertIn("/import wireguard.rsc", data["routeros_command"])

        # Check DB record
        token_obj = ScriptDownloadToken.objects.get(token=data["token"])
        self.assertEqual(token_obj.router, self.router)
        self.assertEqual(token_obj.template, self.template)
        self.assertEqual(token_obj.filename, "wireguard.rsc")
        self.assertTrue(token_obj.include_cleanup)

    def test_non_owner_cannot_generate_bootstrap_token(self):
        """Viewer or unrelated user cannot generate bootstrap tokens."""
        # Viewer (has VIEWER role)
        self.client.force_authenticate(user=self.viewer)
        response = self.client.post(self.router_token_url, data={}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Unrelated user
        self.client.force_authenticate(user=self.unrelated)
        response = self.client.post(self.router_token_url, data={}, format="json")
        # In RouterViewSet.get_queryset, unrelated user doesn't see the router
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_cannot_generate_token(self):
        """Anonymous user cannot access token generation."""
        response = self.client.post(self.router_token_url, data={}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_execution_generate_token_endpoint(self):
        """Execution-level generate-token action creates a single-use token."""
        execution = RouterScriptExecution.objects.create(
            router=self.router,
            template=self.template,
            variables_used={"wg_port": 51820, "pubkey": "key123"},
        )
        url = reverse("scripts:script-executions-generate-token", kwargs={"pk": execution.pk})

        # Owner generates token
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(url, data={}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("token", response.data["data"])

        # Viewer cannot generate token
        self.client.force_authenticate(user=self.viewer)
        resp_viewer = self.client.post(url, data={}, format="json")
        self.assertEqual(resp_viewer.status_code, status.HTTP_403_FORBIDDEN)

    def test_download_script_burn_on_read(self):
        """Script download endpoint serves .rsc and burns token immediately."""
        token_record = ScriptDownloadToken.objects.create(
            router=self.router,
            template=self.template,
            variables_used={"wg_port": 51820, "pubkey": "supersecretkey"},
            token="burn-me-after-reading",
            filename="vpn_init.rsc",
            expires_at=timezone.now() + timedelta(minutes=10),
            include_cleanup=True,
        )
        download_url = reverse("scripts:script-download", kwargs={"token": token_record.token})

        # Public access without auth (RouterOS fetch client)
        response = self.client.get(download_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "text/plain; charset=utf-8")
        self.assertEqual(response["Content-Disposition"], 'attachment; filename="vpn_init.rsc"')

        content = response.content.decode("utf-8")
        self.assertIn("listen-port=51820", content)
        self.assertIn('public-key="supersecretkey"', content)
        self.assertIn('/file remove [find name="vpn_init.rsc"]', content)

        # Verify token is burned in DB
        token_record.refresh_from_db()
        self.assertTrue(token_record.is_consumed)
        self.assertIsNotNone(token_record.consumed_at)

        # Second download attempt must fail with 410 Gone (Burn-on-Read)
        second_response = self.client.get(download_url)
        self.assertEqual(second_response.status_code, status.HTTP_410_GONE)
        self.assertEqual(second_response.data["error"]["code"], "token_invalid_or_expired")

    def test_download_expired_or_nonexistent_token_returns_410(self):
        """Expired or non-existent tokens return HTTP 410 Gone."""
        # Non-existent
        url_nonexistent = reverse("scripts:script-download", kwargs={"token": "does-not-exist"})
        resp_nonexistent = self.client.get(url_nonexistent)
        self.assertEqual(resp_nonexistent.status_code, status.HTTP_410_GONE)

        # Expired
        expired_token = ScriptDownloadToken.objects.create(
            router=self.router,
            token="already-expired",
            expires_at=timezone.now() - timedelta(minutes=5),
        )
        url_expired = reverse("scripts:script-download", kwargs={"token": expired_token.token})
        resp_expired = self.client.get(url_expired)
        self.assertEqual(resp_expired.status_code, status.HTTP_410_GONE)

    def test_download_token_i18n(self):
        """Verify error messages respect Accept-Language for Spanish and English."""
        download_url = reverse("scripts:script-download", kwargs={"token": "nonexistent-token"})

        # Spanish
        resp_es = self.client.get(download_url, HTTP_ACCEPT_LANGUAGE="es")
        self.assertEqual(resp_es.status_code, status.HTTP_410_GONE)
        self.assertEqual(resp_es.headers.get("Content-Language"), "es")
        self.assertEqual(
            resp_es.data["error"]["detail"],
            "El enlace de script de aprovisionamiento es inválido, ha expirado o ya ha sido utilizado.",
        )

        # English
        resp_en = self.client.get(download_url, HTTP_ACCEPT_LANGUAGE="en")
        self.assertEqual(resp_en.status_code, status.HTTP_410_GONE)
        self.assertEqual(resp_en.headers.get("Content-Language"), "en")
        self.assertEqual(
            resp_en.data["error"]["detail"],
            "The provisioning script link is invalid, has expired, or has already been used.",
        )

