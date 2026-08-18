from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

class AnalyticsEventIn(BaseModel):
    """
    Schema for ingesting a single analytics event.
    """
    event_name: str = Field(..., description="Unique event identifier, e.g. 'purchase_completed'", max_length=255)
    event_category: Optional[str] = Field(None, description="Category such as 'ecommerce', 'navigation'", max_length=100)
    user_id: Optional[str] = Field(None, description="Authenticated user identifier", max_length=255)
    session_id: Optional[str] = Field(None, description="Client session UUID", max_length=255)
    platform: Optional[str] = Field(None, description="Operating system / platform ('android', 'ios', 'web')", max_length=50)
    app_version: Optional[str] = Field(None, description="Client application version, e.g. '1.2.0'", max_length=50)
    os_version: Optional[str] = Field(None, description="OS version, e.g. 'Android 14', 'iOS 17.2'", max_length=50)
    device_model: Optional[str] = Field(None, description="Device model string, e.g. 'Pixel 7'", max_length=100)
    properties: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Arbitrary custom properties payload")
    occurred_at: Optional[datetime] = Field(default=None, description="ISO timestamp when the event occurred on the client")

    class Config:
        json_schema_extra = {
            "example": {
                "event_name": "screen_view",
                "event_category": "navigation",
                "user_id": "usr_987654",
                "session_id": "sess_abc123",
                "platform": "android",
                "app_version": "1.0.0",
                "os_version": "Android 14",
                "device_model": "Google Pixel 7",
                "properties": {
                    "screen_name": "checkout_screen",
                    "source": "home_banner"
                },
                "occurred_at": "2026-08-18T14:30:00Z"
            }
        }

class AnalyticsEventBatchIn(BaseModel):
    """
    Schema for batch event ingestion.
    """
    events: List[AnalyticsEventIn] = Field(..., min_length=1, max_length=500, description="List of events to record in bulk")

class AnalyticsEventResponse(BaseModel):
    """
    Standard response after event recording.
    """
    success: bool = True
    message: str = "Event tracked successfully."
    event_id: Optional[str] = None
    events_count: Optional[int] = None

class MetricCount(BaseModel):
    name: str
    total: int

class AnalyticsMetricsResponse(BaseModel):
    """
    Aggregated metrics response.
    """
    success: bool = True
    period_days: int
    total_events: int
    unique_users: int
    top_events: List[Dict[str, Any]]
    platforms: List[Dict[str, Any]]
