"""
Sub-domain tests: Jinja2 Script Template Rendering.
"""

from django.test import TestCase

from apps.routers.models import Router
from apps.scripts.models import RouterScriptExecution, ScriptTemplate


class ScriptRenderingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.router = Router.objects.create(
            name="Test Router",
            host="192.168.1.1",
            port=443,
            api_username="admin",
            api_password="password",
        )
        cls.template = ScriptTemplate.objects.create(
            name="Test Template",
            content="/ip address add address={{ ip_address }} interface={{ interface }}",
        )

    def test_script_rendered_content(self):
        """Test that the script is correctly rendered with Jinja2 variables."""
        execution = RouterScriptExecution.objects.create(
            router=self.router,
            template=self.template,
            variables_used={
                "ip_address": "10.0.0.1/24",
                "interface": "ether1",
            },
        )
        expected_content = "/ip address add address=10.0.0.1/24 interface=ether1"
        self.assertEqual(execution.rendered_content, expected_content)

    def test_script_rendered_content_no_template(self):
        """Test rendering when no template is associated."""
        execution = RouterScriptExecution.objects.create(
            router=self.router,
            template=None,
            variables_used={"any": "var"},
        )
        self.assertEqual(execution.rendered_content, "")

    def test_script_rendered_content_missing_variables(self):
        """Test rendering when some variables are missing."""
        execution = RouterScriptExecution.objects.create(
            router=self.router,
            template=self.template,
            variables_used={"ip_address": "10.0.0.1/24"},
        )
        expected_content = "/ip address add address=10.0.0.1/24 interface="
        self.assertEqual(execution.rendered_content, expected_content)
