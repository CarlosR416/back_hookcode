"""
Database router for the RADIUS domain.

Directs all read and write operations for apps.radius models to the 'radius'
database connection, while strictly preventing Django from attempting migrations
on the unmanaged FreeRADIUS schema.
"""

from typing import Any, Type
from django.db.models import Model


class RadiusDatabaseRouter:
    """
    A database router to control all database operations on models in the
    RADIUS application.
    """

    route_app_labels = {"radius"}

    def db_for_read(self, model: Type[Model], **hints: Any) -> str | None:
        """Point read operations for RADIUS models to the 'radius' database."""
        if model._meta.app_label in self.route_app_labels:
            return "radius"
        return None

    def db_for_write(self, model: Type[Model], **hints: Any) -> str | None:
        """Point write operations for RADIUS models to the 'radius' database."""
        if model._meta.app_label in self.route_app_labels:
            return "radius"
        return None

    def allow_relation(self, obj1: Model, obj2: Model, **hints: Any) -> bool | None:
        """Allow relations if both models are in the RADIUS app or neither is."""
        if (
            obj1._meta.app_label in self.route_app_labels
            or obj2._meta.app_label in self.route_app_labels
        ):
            return obj1._meta.app_label == obj2._meta.app_label
        return None

    def allow_migrate(
        self, db: str, app_label: str, model_name: str | None = None, **hints: Any
    ) -> bool | None:
        """
        Ensure that the RADIUS app never runs migrations against any database.
        The FreeRADIUS schema is unmanaged and managed externally.
        """
        if app_label in self.route_app_labels:
            return False
        return None
