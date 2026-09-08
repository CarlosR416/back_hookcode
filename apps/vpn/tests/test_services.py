"""
Unit tests for VpnNodeService.
"""

from django.core.exceptions import ObjectDoesNotExist
from django.test import TestCase

from apps.vpn.models import VpnNode
from apps.vpn.services import VpnNodeService


class VpnNodeServiceTests(TestCase):
    def setUp(self):
        self.cert_sample = (
            "-----BEGIN CERTIFICATE-----\n"
            "MIICpDCCAYwCCQC1...SAMPLE...CERTIFICATE\n"
            "-----END CERTIFICATE-----"
        )
        self.node = VpnNode.objects.create(
            name="vpn-gateway-01",
            host="vpn.wifitickets.com",
            port=51820,
            vpn_type=VpnNode.VpnType.WIREGUARD,
            public_certificate=self.cert_sample,
            is_active=True,
        )
        self.inactive_node = VpnNode.objects.create(
            name="vpn-gateway-disabled",
            host="disabled.wifitickets.com",
            port=51820,
            vpn_type=VpnNode.VpnType.OPENVPN,
            public_certificate="SOME_PUB_KEY",
            is_active=False,
        )

    def test_get_public_certificate_by_instance(self):
        """Verify fetching public certificate passing a VpnNode instance."""
        cert = VpnNodeService.get_public_certificate(self.node)
        self.assertEqual(cert, self.cert_sample.strip())

    def test_get_public_certificate_by_id(self):
        """Verify fetching public certificate by integer ID."""
        cert = VpnNodeService.get_public_certificate(self.node.pk)
        self.assertEqual(cert, self.cert_sample.strip())

    def test_get_public_certificate_by_name(self):
        """Verify fetching public certificate by node name."""
        cert = VpnNodeService.get_public_certificate("vpn-gateway-01")
        self.assertEqual(cert, self.cert_sample.strip())

    def test_get_public_certificate_inactive_node_raises_error(self):
        """Verify inactive node cannot serve certificates."""
        with self.assertRaises(ValueError):
            VpnNodeService.get_public_certificate(self.inactive_node)

        with self.assertRaises(ObjectDoesNotExist):
            VpnNodeService.get_public_certificate(self.inactive_node.pk)

        with self.assertRaises(ObjectDoesNotExist):
            VpnNodeService.get_public_certificate("vpn-gateway-disabled")

    def test_get_public_certificate_non_existent_node(self):
        """Verify querying non-existent node raises ObjectDoesNotExist."""
        with self.assertRaises(ObjectDoesNotExist):
            VpnNodeService.get_public_certificate(999999)

        with self.assertRaises(ObjectDoesNotExist):
            VpnNodeService.get_public_certificate("non-existent-node")

    def test_get_public_certificate_empty_raises_error(self):
        """Verify node with empty certificate raises ValueError."""
        empty_node = VpnNode.objects.create(
            name="empty-cert-node",
            host="empty.wifitickets.com",
            port=51820,
            public_certificate="",
            is_active=True,
        )
        with self.assertRaises(ValueError):
            VpnNodeService.get_public_certificate(empty_node)

    def test_get_node_details(self):
        """Verify retrieving structured node details."""
        details = VpnNodeService.get_node_details(self.node)
        self.assertEqual(details["id"], self.node.pk)
        self.assertEqual(details["name"], "vpn-gateway-01")
        self.assertEqual(details["host"], "vpn.wifitickets.com")
        self.assertEqual(details["port"], 51820)
        self.assertEqual(details["vpn_type"], VpnNode.VpnType.WIREGUARD)
        self.assertEqual(details["public_certificate"], self.cert_sample.strip())
        self.assertTrue(details["is_active"])
