"""
API integration tests for VpnNodeViewSet.
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.vpn.models import VpnNode

User = get_user_model()


class VpnNodeApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_user = User.objects.create_superuser(
            username="vpn_admin",
            email="admin@wifitickets.com",
            password="adminpassword123",
        )
        cls.regular_user = User.objects.create_user(
            username="vpn_client",
            email="client@wifitickets.com",
            password="userpassword123",
        )
        cls.cert_sample = (
            "-----BEGIN CERTIFICATE-----\n"
            "MIICpDCCAYwCCQC1...SAMPLE...CERTIFICATE\n"
            "-----END CERTIFICATE-----"
        )
        cls.node = VpnNode.objects.create(
            name="node-chile-01",
            host="cl.vpn.wifitickets.com",
            port=51820,
            vpn_type=VpnNode.VpnType.WIREGUARD,
            public_certificate=cls.cert_sample,
            is_active=True,
        )
        cls.inactive_node = VpnNode.objects.create(
            name="node-maintenance",
            host="maint.vpn.wifitickets.com",
            port=51820,
            vpn_type=VpnNode.VpnType.OPENVPN,
            public_certificate="MAINTENANCE_PUB_CERT",
            is_active=False,
        )
        cls.list_url = reverse("vpn:nodes-list")
        cls.detail_url = reverse("vpn:nodes-detail", kwargs={"pk": cls.node.pk})
        cls.cert_url = reverse("vpn:nodes-certificate", kwargs={"pk": cls.node.pk})

    def test_regular_user_can_retrieve_certificate_json(self):
        """Authenticated user can fetch the node certificate as JSON."""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(self.cert_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("data", response.data)
        data = response.data["data"]
        self.assertEqual(data["node_id"], self.node.pk)
        self.assertEqual(data["name"], "node-chile-01")
        self.assertEqual(data["vpn_type"], VpnNode.VpnType.WIREGUARD)
        self.assertEqual(data["public_certificate"], self.cert_sample.strip())

    def test_regular_user_can_retrieve_certificate_raw(self):
        """Authenticated user can fetch the raw certificate stream with ?raw=true."""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(f"{self.cert_url}?raw=true")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("text/plain", response["Content-Type"])
        self.assertEqual(response.content.decode("utf-8"), self.cert_sample.strip())

    def test_unauthenticated_cannot_access_certificate(self):
        """Unauthenticated requests are rejected with 401."""
        response = self.client.get(self.cert_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_can_create_vpn_node(self):
        """Staff user can register a new VPN node."""
        self.client.force_authenticate(user=self.admin_user)
        payload = {
            "name": "node-us-east",
            "host": "us.vpn.wifitickets.com",
            "port": 51820,
            "internal_ip": "10.10.0.1/24",
            "vpn_type": VpnNode.VpnType.WIREGUARD,
            "public_certificate": "US_WIREGUARD_PUB_KEY",
            "description": "Primary US gateway",
        }
        response = self.client.post(self.list_url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = VpnNode.objects.get(name="node-us-east")
        self.assertEqual(created.internal_ip, "10.10.0.1/24")

    def test_regular_user_cannot_create_vpn_node(self):
        """Non-staff users cannot register VPN nodes."""
        self.client.force_authenticate(user=self.regular_user)
        payload = {
            "name": "hacked-node",
            "host": "hack.com",
            "port": 51820,
            "public_certificate": "KEY",
        }
        response = self.client.post(self.list_url, data=payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_regular_user_only_sees_active_nodes(self):
        """Regular users only see active nodes in list."""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_names = [n["name"] for n in response.data["results"]]
        self.assertIn("node-chile-01", returned_names)
        self.assertNotIn("node-maintenance", returned_names)

    def test_inactive_node_certificate_not_found_for_regular_user(self):
        """Requesting certificate for an inactive node returns 404 for regular users."""
        self.client.force_authenticate(user=self.regular_user)
        inactive_cert_url = reverse(
            "vpn:nodes-certificate", kwargs={"pk": self.inactive_node.pk}
        )
        response = self.client.get(inactive_cert_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
