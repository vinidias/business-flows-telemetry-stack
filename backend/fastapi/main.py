import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from collections import Counter

from fastapi import FastAPI, Request, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from models import (
    AnalyticsEventIn,
    AnalyticsEventBatchIn,
    AnalyticsEventResponse,
    AnalyticsMetricsResponse,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("telemetry_api")

app = FastAPI(
    title="Business Flows Telemetry Stack API",
    description="Generic, high-performance telemetry ingestion API for mobile, web, and microservices.",
    version="1.0.0",
)

# Enable CORS for cross-origin mobile/web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for demonstration / lightweight usage.
# Replace with PostgreSQL, ClickHouse, or MongoDB in high-scale production.
IN_MEMORY_EVENTS: List[Dict[str, Any]] = []


def _extract_request_metadata(request: Request) -> Dict[str, str]:
    """Helper to extract IP address and User-Agent from incoming HTTP request."""
    client_ip = request.client.host if request.client else ""
    # Check for proxy forwarding
    if "x-forwarded-for" in request.headers:
        client_ip = request.headers["x-forwarded-for"].split(",")[0].strip()

    user_agent = request.headers.get("user-agent", "")
    return {"ip_address": client_ip, "user_agent": user_agent}


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for load balancers and orchestrators."""
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post(
    "/api/analytics/event",
    response_model=AnalyticsEventResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Analytics"],
)
async def track_event(payload: AnalyticsEventIn, request: Request):
    """
    Ingest a single telemetry event.
    Automatically captures client IP, User-Agent, and timestamps.
    """
    metadata = _extract_request_metadata(request)
    event_id = str(uuid.uuid4())
    occurred_at = payload.occurred_at or datetime.now(timezone.utc)

    record = {
        "id": event_id,
        "event_name": payload.event_name,
        "event_category": payload.event_category,
        "user_id": payload.user_id,
        "session_id": payload.session_id,
        "platform": payload.platform,
        "app_version": payload.app_version,
        "os_version": payload.os_version,
        "device_model": payload.device_model,
        "properties": payload.properties,
        "ip_address": metadata["ip_address"],
        "user_agent": metadata["user_agent"],
        "occurred_at": occurred_at,
        "created_at": datetime.now(timezone.utc),
    }

    # Store event (Replace with DB insert)
    IN_MEMORY_EVENTS.append(record)
    logger.info(f"Event recorded: {payload.event_name} (user: {payload.user_id or 'anon'}, platform: {payload.platform})")

    return AnalyticsEventResponse(
        success=True,
        message="Event tracked successfully.",
        event_id=event_id,
    )


@app.post(
    "/api/analytics/events/batch",
    response_model=AnalyticsEventResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Analytics"],
)
async def track_batch_events(payload: AnalyticsEventBatchIn, request: Request):
    """
    Ingest a batch of telemetry events in a single HTTP call.
    Ideal for mobile apps flushing offline event queues.
    """
    metadata = _extract_request_metadata(request)
    now = datetime.now(timezone.utc)
    created_count = 0

    for item in payload.events:
        event_id = str(uuid.uuid4())
        record = {
            "id": event_id,
            "event_name": item.event_name,
            "event_category": item.event_category,
            "user_id": item.user_id,
            "session_id": item.session_id,
            "platform": item.platform,
            "app_version": item.app_version,
            "os_version": item.os_version,
            "device_model": item.device_model,
            "properties": item.properties,
            "ip_address": metadata["ip_address"],
            "user_agent": metadata["user_agent"],
            "occurred_at": item.occurred_at or now,
            "created_at": now,
        }
        IN_MEMORY_EVENTS.append(record)
        created_count += 1

    logger.info(f"Batch events recorded: {created_count} items")

    return AnalyticsEventResponse(
        success=True,
        message="Batch events tracked successfully.",
        events_count=created_count,
    )


@app.get(
    "/api/analytics/metrics",
    response_model=AnalyticsMetricsResponse,
    tags=["Analytics"],
)
async def get_metrics(days: int = Query(30, ge=1, le=365, description="Number of past days to query")):
    """
    Query summary telemetry metrics for analytics dashboards.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    filtered = [
        e for e in IN_MEMORY_EVENTS
        if e["occurred_at"] >= cutoff
    ]

    total_events = len(filtered)
    unique_users = len({e["user_id"] for e in filtered if e["user_id"] is not None})

    event_counts = Counter(e["event_name"] for e in filtered)
    top_events = [{"event_name": name, "total": count} for name, count in event_counts.most_common(10)]

    platform_counts = Counter(e["platform"] or "unknown" for e in filtered)
    platforms = [{"platform": plat, "total": count} for plat, count in platform_counts.most_common()]

    return AnalyticsMetricsResponse(
        success=True,
        period_days=days,
        total_events=total_events,
        unique_users=unique_users,
        top_events=top_events,
        platforms=platforms,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
