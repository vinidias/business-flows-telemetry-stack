import json
import logging
from datetime import datetime, timedelta
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.db.models import Count
from .models import AnalyticsEvent

logger = logging.getLogger(__name__)

def _get_client_ip(request) -> str:
    """Extract client IP handling proxies / load balancers."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')

@csrf_exempt
def track_event(request):
    """
    Ingest a single telemetry event.
    Endpoint: POST /api/analytics/event
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        body = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid JSON body"}, status=400)

    event_name = body.get("event_name")
    if not event_name or not isinstance(event_name, str):
        return JsonResponse({"success": False, "message": "Missing required field: event_name"}, status=422)

    # Detect user_id from auth if not passed
    user_id = body.get("user_id")
    if not user_id and hasattr(request, "user") and request.user.is_authenticated:
        user_id = str(request.user.pk)

    # Parse occurred_at
    occurred_at_str = body.get("occurred_at")
    occurred_at = parse_datetime(occurred_at_str) if occurred_at_str else timezone.now()
    if occurred_at is None:
        occurred_at = timezone.now()

    try:
        event = AnalyticsEvent.objects.create(
            event_name=event_name,
            event_category=body.get("event_category"),
            user_id=user_id,
            session_id=body.get("session_id"),
            platform=body.get("platform"),
            app_version=body.get("app_version"),
            os_version=body.get("os_version"),
            device_model=body.get("device_model"),
            properties=body.get("properties"),
            ip_address=_get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            occurred_at=occurred_at,
        )

        return JsonResponse({
            "success": True,
            "message": "Event tracked successfully.",
            "event_id": event.id
        }, status=201)

    except Exception as e:
        logger.exception("Error recording analytics event: %s", e)
        return JsonResponse({"success": False, "message": "Internal server error"}, status=500)

@csrf_exempt
def track_batch_events(request):
    """
    Ingest a batch of telemetry events.
    Endpoint: POST /api/analytics/events/batch
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        body = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "message": "Invalid JSON body"}, status=400)

    events_data = body.get("events")
    if not isinstance(events_data, list) or len(events_data) == 0:
        return JsonResponse({"success": False, "message": "Field 'events' must be a non-empty list"}, status=422)

    auth_user_id = str(request.user.pk) if hasattr(request, "user") and request.user.is_authenticated else None
    ip = _get_client_ip(request)
    ua = request.META.get('HTTP_USER_AGENT', '')
    now = timezone.now()

    events_to_create = []
    for item in events_data:
        event_name = item.get("event_name")
        if not event_name:
            continue

        occurred_at_str = item.get("occurred_at")
        occurred_at = parse_datetime(occurred_at_str) if occurred_at_str else now

        events_to_create.append(
            AnalyticsEvent(
                event_name=event_name,
                event_category=item.get("event_category"),
                user_id=item.get("user_id") or auth_user_id,
                session_id=item.get("session_id"),
                platform=item.get("platform"),
                app_version=item.get("app_version"),
                os_version=item.get("os_version"),
                device_model=item.get("device_model"),
                properties=item.get("properties"),
                ip_address=ip,
                user_agent=ua,
                occurred_at=occurred_at or now,
            )
        )

    try:
        created = AnalyticsEvent.objects.bulk_create(events_to_create)
        return JsonResponse({
            "success": True,
            "message": "Batch events tracked successfully.",
            "events_count": len(created)
        }, status=201)
    except Exception as e:
        logger.exception("Error during batch event creation: %s", e)
        return JsonResponse({"success": False, "message": "Internal server error"}, status=500)

def analytics_metrics(request):
    """
    Get aggregated metrics for the last N days.
    Endpoint: GET /api/analytics/metrics
    """
    try:
        days = int(request.GET.get("days", 30))
    except ValueError:
        days = 30

    since = timezone.now() - timedelta(days=days)
    queryset = AnalyticsEvent.objects.filter(occurred_at__gte=since)

    total_events = queryset.count()
    unique_users = queryset.exclude(user_id__isnull=True).values("user_id").distinct().count()

    top_events = list(
        queryset.values("event_name")
        .annotate(total=Count("id"))
        .order_by("-total")[:10]
    )

    platform_breakdown = list(
        queryset.values("platform")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    return JsonResponse({
        "success": True,
        "period_days": days,
        "total_events": total_events,
        "unique_users": unique_users,
        "top_events": top_events,
        "platforms": platform_breakdown,
    })
