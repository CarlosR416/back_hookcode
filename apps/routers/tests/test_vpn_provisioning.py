"""
Sub-domain tests: Automated IKEv2 VPN Client Provisioning for Routers.
"""

from datetime import timedelta
from django.contrib.auth import get_user_model
from django.db import connections
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.radius.models import RadAcct, RadCheck, RadReply, RadUserGroup
from apps.routers.models import Router, UserRouter
from apps.routers.services import provision_router_defaults, sync_router_radius_user
from apps.scripts.models import ScriptTemplate
from apps.vpn.models import VpnNode

User = get_user_model()


class RouterVpnProvisioningTests(APITestCase):
    databases = {"default", "radius"}

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._radius_models = [RadCheck, RadReply, RadUserGroup, RadAcct]
        with connections["radius"].schema_editor() as editor:
            for model in cls._radius_models:
                editor.create_model(model)

    @classmethod
    def tearDownClass(cls):
        with connections["radius"].schema_editor() as editor:
            for model in reversed(cls._radius_models):
                editor.delete_model(model)
        super().tearDownClass()

    def setUp(self):
        self.owner = User.objects.create_user(
            username="vpn_owner",
            email="owner@wifitickets.com",
            password="ownerpassword123",
        )
        self.viewer = User.objects.create_user(
            username="vpn_viewer",
            email="viewer@wifitickets.com",
            password="viewerpassword123",
        )
        self.unrelated = User.objects.create_user(
            username="vpn_stranger",
            email="stranger@wifitickets.com",
            password="strangerpassword123",
        )

        defaults = provision_router_defaults()
        self.router = Router.objects.create(name="MikroTik-Branch-01", **defaults)
        UserRouter.objects.create(
            user=self.owner,
            router=self.router,
            role=UserRouter.RouterRole.OWNER,
        )
        UserRouter.objects.create(
            user=self.viewer,
            router=self.router,
            role=UserRouter.RouterRole.VIEWER,
        )
        # Sync router FreeRADIUS user to create RadCheck credentials
        self.radius_creds = sync_router_radius_user(self.router)

        # Create active VPN node
        self.cert_content = "-----BEGIN CERTIFICATE-----\nMIICvDCCAaQCCQD...\n-----END CERTIFICATE-----"
        self.vpn_node = VpnNode.objects.create(
            name="vpn-core-frankfurt",
            host="35.170.65.8",
            port=500,
            internal_ip="10.8.0.1/24",
            vpn_type=VpnNode.VpnType.IPSEC,
            public_certificate=self.cert_content,
            is_active=True,
        )

        # Ensure the seeded template exists in the test DB
        self.template, _ = ScriptTemplate.objects.get_or_create(
            name="MikroTik IKEv2 VPN Client",
            defaults={
                "description": "IKEv2 client provisioning script",
                "content": (
                    '# 1. Download and import VPN server certificate\n'
                    '/tool fetch url="{{ cert_download_url }}" mode=https dst-path="IKEv2-cert.pem";\n'
                    ':delay 2s;\n'
                    '/certificate import file-name=IKEv2-cert.pem passphrase="";\n'
                    ':delay 1s;\n\n'
                    '# 2. IPsec Profile\n'
                    '/ip ipsec profile\n'
                    'add name=profile-ikev2 dh-group=ecp256,modp2048 enc-algorithm=aes-256 hash-algorithm=sha256\n\n'
                    '# 3. IPsec Proposal\n'
                    '/ip ipsec proposal\n'
                    'add name=proposal-ikev2 auth-algorithms=sha256 enc-algorithms=aes-256-cbc pfs-group=none\n\n'
                    '# 4. IPsec Peer\n'
                    '/ip ipsec peer\n'
                    'add name=peer-ikev2 address={{ vpn_server_address }} profile=profile-ikev2 exchange-mode=ike2\n\n'
                    '# 5. IPsec Mode Config\n'
                    '/ip ipsec mode-config\n'
                    'add name=ikev2-request-ip responder=no\n\n'
                    '# 6. IPsec Identity (Dynamic RADIUS credentials)\n'
                    '/ip ipsec identity\n'
                    'add peer=peer-ikev2 auth-method=eap certificate="IKEv2-cert.pem_0" \\\n'
                    '    eap-methods=eap-mschapv2 username="{{ radius_username }}" password="{{ radius_password }}" \\\n'
                    '    generate-policy=port-strict mode-config=ikev2-request-ip\n\n'
                    '# 7. Firewall filter rule (placed first in the input chain)\n'
                    '/ip firewall filter\n'
                    'add chain=input src-address={{ vpn_server_internal_ip }} action=accept comment="Allow VPN Server traffic" place-before=0\n'
                ),
            },
        )

        self.generate_url = reverse(
            "routers:routers-generate-vpn-token", kwargs={"pk": self.router.pk}
        )

    def test_owner_can_generate_vpn_token(self):
        """Router owner can generate an automated VPN provisioning token and RouterOS command."""
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(self.generate_url, data={}, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.data["data"]
        self.assertIn("token", data)
        self.assertIn("download_url", data)
        self.assertIn("routeros_command", data)
        self.assertIn("expires_at", data)

        # Validate RouterOS command format
        expected_cmd_prefix = f'/tool fetch url="{data["download_url"]}" mode=https dst-path="vpn_setup.rsc"; :delay 1s; /import vpn_setup.rsc'
        self.assertEqual(data["routeros_command"], expected_cmd_prefix)

    def test_rendered_script_contents_and_burn_on_read(self):
        """
        Downloading the script via token renders all dynamic VPN and FreeRADIUS variables,
        and burns the token immediately upon completion.
        """
        self.client.force_authenticate(user=self.owner)
        token_resp = self.client.post(self.generate_url, data={"filename": "vpn_custom.rsc"}, format="json")
        self.assertEqual(token_resp.status_code, status.HTTP_201_CREATED)

        download_url = token_resp.data["data"]["download_url"]
        token = token_resp.data["data"]["token"]

        # 1. Unauthenticated download (simulates MikroTik /tool fetch)
        self.client.logout()
        script_resp = self.client.get(download_url)
        self.assertEqual(script_resp.status_code, status.HTTP_200_OK)
        self.assertIn("text/plain", script_resp["Content-Type"])

        content = script_resp.content.decode("utf-8")

        # Certificate download & import
        expected_cert_url = f"/api/vpn/nodes/{self.vpn_node.pk}/certificate/?raw=true"
        self.assertIn(f'/tool fetch url="http://testserver{expected_cert_url}" mode=https dst-path="IKEv2-cert.pem";', content)
        self.assertIn('/certificate import file-name=IKEv2-cert.pem passphrase="";', content)

        # Peer configuration with VPN server host
        self.assertIn(f"address={self.vpn_node.host}", content)

        # Identity configuration with FreeRADIUS username and password
        self.assertIn(f'username="{self.router.api_username}"', content)
        self.assertIn(f'password="{self.radius_creds["password"]}"', content)

        # Firewall rule placed first with stripped internal IP
        self.assertIn("src-address=10.8.0.1 action=accept comment=\"Allow VPN Server traffic\" place-before=0", content)

        # Self-cleanup
        self.assertIn('/file remove [find name="vpn_custom.rsc"];', content)

        # 2. Token burn verification (Burn-on-Read: second download returns 410)
        second_resp = self.client.get(download_url)
        self.assertEqual(second_resp.status_code, status.HTTP_410_GONE)

    def test_unauthenticated_can_download_vpn_certificate_for_routeros(self):
        """Public certificate endpoint allows unauthenticated downloads with ?raw=true."""
        cert_url = reverse("vpn:nodes-certificate", kwargs={"pk": self.vpn_node.pk})
        response = self.client.get(f"{cert_url}?raw=true")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.content.decode("utf-8"), self.cert_content)

    def test_viewer_cannot_generate_vpn_token(self):
        """Viewer role receives HTTP 403 when attempting to generate a VPN token."""
        self.client.force_authenticate(user=self.viewer)
        response = self.client.post(self.generate_url, data={}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unrelated_user_cannot_generate_vpn_token(self):
        """User without any router role receives HTTP 404 or 403."""
        self.client.force_authenticate(user=self.unrelated)
        response = self.client.post(self.generate_url, data={}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_cannot_generate_vpn_token(self):
        """Unauthenticated user receives HTTP 401."""
        response = self.client.post(self.generate_url, data={}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_no_active_vpn_node_returns_400(self):
        """If no VPN nodes are active, endpoint returns HTTP 400 with descriptive error."""
        VpnNode.objects.update(is_active=False)
        self.client.force_authenticate(user=self.owner)
        response = self.client.post(self.generate_url, data={}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["code"], "vpn_provisioning_error")

    def test_router_vpn_connection_status_never_connected(self):
        """When no radacct records exist, status is NEVER_CONNECTED both internally and in API."""
        # 1. Internal model properties (Option B)
        self.assertFalse(self.router.is_vpn_connected)
        self.assertEqual(self.router.vpn_status, "NEVER_CONNECTED")
        self.assertIsNone(self.router.vpn_tunnel_ip)

        # 2. API response representation (Option A)
        self.client.force_authenticate(user=self.owner)
        detail_url = reverse("routers:routers-detail", kwargs={"pk": self.router.pk})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        vpn_info = response.data["data"]["vpn_connection"]
        self.assertEqual(vpn_info["status"], "NEVER_CONNECTED")
        self.assertFalse(vpn_info["is_connected"])
        self.assertIsNone(vpn_info["tunnel_ip"])
        self.assertIsNone(vpn_info["connected_at"])
        self.assertIsNone(vpn_info["last_seen"])

    def test_router_vpn_connection_status_connected(self):
        """When an active radacct session exists (acctstoptime IS NULL), status is CONNECTED."""
        now = timezone.now()
        RadAcct.objects.create(
            acctsessionid="sess-vpn-01",
            acctuniqueid="uniq-vpn-01",
            username=self.router.api_username,
            nasipaddress="35.170.65.8",
            acctstarttime=now,
            acctstoptime=None,
            framedipaddress="10.8.0.2",
        )

        # 1. Internal model properties (Option B)
        self.assertTrue(self.router.is_vpn_connected)
        self.assertEqual(self.router.vpn_status, "CONNECTED")
        self.assertEqual(self.router.vpn_tunnel_ip, "10.8.0.2")

        # 2. API response representation (Option A)
        self.client.force_authenticate(user=self.owner)
        detail_url = reverse("routers:routers-detail", kwargs={"pk": self.router.pk})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        vpn_info = response.data["data"]["vpn_connection"]
        self.assertEqual(vpn_info["status"], "CONNECTED")
        self.assertTrue(vpn_info["is_connected"])
        self.assertEqual(vpn_info["tunnel_ip"], "10.8.0.2")
        self.assertIsNotNone(vpn_info["connected_at"])
        self.assertIsNone(vpn_info["last_seen"])

    def test_router_vpn_connection_status_disconnected(self):
        """When sessions exist but all have acctstoptime set, status is DISCONNECTED with last_seen."""
        start_time = timezone.now() - timedelta(hours=3)
        stop_time = timezone.now() - timedelta(hours=1)
        RadAcct.objects.create(
            acctsessionid="sess-vpn-closed",
            acctuniqueid="uniq-vpn-closed",
            username=self.router.api_username,
            nasipaddress="35.170.65.8",
            acctstarttime=start_time,
            acctstoptime=stop_time,
            framedipaddress="10.8.0.5",
        )

        # 1. Internal model properties (Option B)
        self.assertFalse(self.router.is_vpn_connected)
        self.assertEqual(self.router.vpn_status, "DISCONNECTED")
        self.assertEqual(self.router.vpn_tunnel_ip, "10.8.0.5")

        # 2. API response representation (Option A)
        self.client.force_authenticate(user=self.owner)
        detail_url = reverse("routers:routers-detail", kwargs={"pk": self.router.pk})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        vpn_info = response.data["data"]["vpn_connection"]
        self.assertEqual(vpn_info["status"], "DISCONNECTED")
        self.assertFalse(vpn_info["is_connected"])
        self.assertEqual(vpn_info["tunnel_ip"], "10.8.0.5")
        self.assertIsNotNone(vpn_info["last_seen"])

    def test_router_list_batch_vpn_connection_status(self):
        """Router list endpoint batch-populates VPN status and omits internal IPs (host and tunnel_ip)."""
        self.client.force_authenticate(user=self.owner)
        list_url = reverse("routers:routers-list")
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        results = response.data.get("results", response.data.get("data", []))
        self.assertTrue(len(results) >= 1)
        router_data = next(r for r in results if r["id"] == self.router.pk)
        self.assertIn("vpn_connection", router_data)
        self.assertEqual(router_data["vpn_connection"]["status"], "NEVER_CONNECTED")

        # Internal IPs MUST NOT be leaked in the list endpoint
        self.assertNotIn("host", router_data)
        self.assertNotIn("tunnel_ip", router_data["vpn_connection"])


