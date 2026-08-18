from django.urls import path
from . import views

"""
Django URL patterns for the Analytics telemetry endpoints.
Include this file in your root `urls.py`:
    path('api/analytics/', include('analytics.urls')),
"""

app_name = 'analytics'

urlpatterns = [
    path('event', views.track_event, name='track_event'),
    path('events/batch', views.track_batch_events, name='track_batch_events'),
    path('metrics', views.analytics_metrics, name='analytics_metrics'),
]
