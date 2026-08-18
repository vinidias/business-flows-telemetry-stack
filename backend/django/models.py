from django.db import models
from django.utils import timezone

class AnalyticsEvent(models.Model):
    """
    Generic Django Model for telemetry and business flow analytics.
    Compatible with PostgreSQL, MySQL, and SQLite.
    """
    # Core event identification
    event_name = models.CharField(max_length=255, db_index=True)
    event_category = models.CharField(max_length=100, null=True, blank=True, db_index=True)

    # Actor & Session identification
    user_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    session_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)

    # Device & Platform telemetry
    platform = models.CharField(max_length=50, null=True, blank=True, db_index=True)
    app_version = models.CharField(max_length=50, null=True, blank=True)
    os_version = models.CharField(max_length=50, null=True, blank=True)
    device_model = models.CharField(max_length=100, null=True, blank=True)

    # Contextual dynamic payload
    properties = models.JSONField(null=True, blank=True)

    # Network metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)

    # Timestamps
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "analytics_events"
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["event_name", "occurred_at"]),
            models.Index(fields=["user_id", "occurred_at"]),
            models.Index(fields=["platform", "occurred_at"]),
        ]

    def __str__(self):
        user = self.user_id or "anonymous"
        return f"[{self.occurred_at:%Y-%m-%d %H:%M:%S}] {self.event_name} (user: {user})"
