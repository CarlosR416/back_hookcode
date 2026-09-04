"""
Firebase utility functions for authenticating users.
"""
from django.utils.translation import gettext as _
from firebase_admin import auth
from rest_framework.exceptions import AuthenticationFailed


def verify_google_token(token: str) -> dict:
    """
    Verifies a Firebase ID token and returns the decoded token payload.
    Raises AuthenticationFailed if the token is invalid or expired.
    """
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception as e:
        raise AuthenticationFailed(_("Invalid Firebase ID token: %(error)s") % {"error": str(e)})
