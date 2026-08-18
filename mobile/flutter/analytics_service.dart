import 'dart:async';
import 'dart:collection';
import 'dart:convert';
import 'dart:io' show Platform;
import 'package:flutter/foundation.dart' show kIsWeb, debugPrint;
import 'package:http/http.dart' as http;

/// {@template analytics_service}
/// Plug-and-play, zero-dependency (only `http`) telemetry & analytics client for Flutter.
/// 
/// Features:
/// - In-memory offline queuing with automatic retry upon connectivity recovery
/// - Automatic platform detection (Android, iOS, Web, macOS, Windows, Linux)
/// - Flexible user identification and persistent custom properties
/// - Standardized telemetry helpers for screen tracking, business conversions, user actions
/// - Configurable via constructor (no hardcoded URLs)
/// {@endtemplate}
class AnalyticsService {
  /// Base API URL (e.g. "https://api.yourdomain.com" or "http://10.0.2.2:8000")
  final String baseUrl;

  /// Optional custom HTTP headers (e.g., Bearer tokens, API keys)
  final Map<String, String>? defaultHeaders;

  /// Application version string (e.g. "1.0.0")
  final String? appVersion;

  /// HTTP client instance (allows mocking in tests)
  final http.Client _httpClient;

  /// In-memory queue of pending events waiting for network delivery
  final Queue<Map<String, dynamic>> _eventQueue = Queue<Map<String, dynamic>>();

  /// Maximum number of events kept in the in-memory queue before dropping oldest
  final int maxQueueSize;

  /// Timer for periodic flushing of queued telemetry events
  Timer? _flushTimer;

  /// Indicates if a batch flush is currently in flight
  bool _isFlushing = false;

  /// Current authenticated user ID (persists across events until cleared)
  String? _userId;

  /// Current active session identifier
  String? _sessionId;

  /// Global user properties attached to every event (e.g., plan: "pro", role: "admin")
  final Map<String, dynamic> _globalProperties = {};

  /// Singleton instance holder for optional global access
  static AnalyticsService? _instance;

  /// Get the configured singleton instance of [AnalyticsService]
  static AnalyticsService get instance {
    assert(
      _instance != null,
      'AnalyticsService has not been initialized. Call AnalyticsService.initialize() first.',
    );
    return _instance!;
  }

  /// Initialize the global singleton instance
  static AnalyticsService initialize({
    required String baseUrl,
    String? appVersion,
    Map<String, String>? defaultHeaders,
    int maxQueueSize = 500,
    Duration flushInterval = const Duration(seconds: 30),
    http.Client? httpClient,
  }) {
    _instance = AnalyticsService(
      baseUrl: baseUrl,
      appVersion: appVersion,
      defaultHeaders: defaultHeaders,
      maxQueueSize: maxQueueSize,
      flushInterval: flushInterval,
      httpClient: httpClient,
    );
    return _instance!;
  }

  /// Constructs an [AnalyticsService] instance.
  AnalyticsService({
    required this.baseUrl,
    this.appVersion,
    this.defaultHeaders,
    this.maxQueueSize = 500,
    Duration flushInterval = const Duration(seconds: 30),
    http.Client? httpClient,
  }) : _httpClient = httpClient ?? http.Client() {
    _startPeriodicFlush(flushInterval);
  }

  // ---------------------------------------------------------------------------
  // User & Session Management
  // ---------------------------------------------------------------------------

  /// Set or update the authenticated [userId].
  /// Pass `null` to clear the identity (e.g., on user logout).
  void setUserId(String? userId) {
    _userId = userId;
    debugPrint('[AnalyticsService] User ID set to: $_userId');
  }

  /// Get the current authenticated user ID.
  String? get userId => _userId;

  /// Set the current [sessionId] for correlation.
  void setSessionId(String? sessionId) {
    _sessionId = sessionId;
  }

  /// Get the current session ID.
  String? get sessionId => _sessionId;

  /// Set global properties that will be merged into every tracked event.
  void setGlobalProperties(Map<String, dynamic> properties) {
    _globalProperties.addAll(properties);
  }

  /// Clear all global properties.
  void clearGlobalProperties() {
    _globalProperties.clear();
  }

  // ---------------------------------------------------------------------------
  // Core Event Tracking
  // ---------------------------------------------------------------------------

  /// Track a generic event with an [eventName], optional [category], and [properties].
  /// 
  /// Example:
  /// ```dart
  /// analytics.trackEvent(
  ///   'export_pdf_clicked',
  ///   category: 'reports',
  ///   properties: {'format': 'pdf', 'pages': 12},
  /// );
  /// ```
  Future<void> trackEvent(
    String eventName, {
    String? category,
    Map<String, dynamic>? properties,
    DateTime? occurredAt,
  }) async {
    final mergedProperties = <String, dynamic>{
      ..._globalProperties,
      if (properties != null) ...properties,
    };

    final payload = <String, dynamic>{
      'event_name': eventName,
      if (category != null) 'event_category': category,
      if (_userId != null) 'user_id': _userId,
      if (_sessionId != null) 'session_id': _sessionId,
      'platform': _detectPlatform(),
      if (appVersion != null) 'app_version': appVersion,
      'properties': mergedProperties,
      'occurred_at': (occurredAt ?? DateTime.now().toUtc()).toIso8601String(),
    };

    _enqueueEvent(payload);
  }

  // ---------------------------------------------------------------------------
  // Convenience Business & Telemetry Helpers
  // ---------------------------------------------------------------------------

  /// Track application opening / startup.
  Future<void> trackAppOpen({Map<String, dynamic>? properties}) {
    return trackEvent(
      'app_open',
      category: 'system',
      properties: properties,
    );
  }

  /// Track screen or page views.
  /// 
  /// Example:
  /// ```dart
  /// analytics.trackScreen('CheckoutScreen', properties: {'cart_items': 3});
  /// ```
  Future<void> trackScreen(
    String screenName, {
    String? previousScreen,
    Map<String, dynamic>? properties,
  }) {
    return trackEvent(
      'screen_view',
      category: 'navigation',
      properties: {
        'screen_name': screenName,
        if (previousScreen != null) 'previous_screen': previousScreen,
        if (properties != null) ...properties,
      },
    );
  }

  /// Track UI button taps or interactions.
  Future<void> trackButtonTap(
    String buttonId, {
    String? screenName,
    Map<String, dynamic>? properties,
  }) {
    return trackEvent(
      'button_tap',
      category: 'interaction',
      properties: {
        'button_id': buttonId,
        if (screenName != null) 'screen_name': screenName,
        if (properties != null) ...properties,
      },
    );
  }

  /// Track business conversion events (e.g. sign up, subscription, lead generation).
  /// 
  /// Example:
  /// ```dart
  /// analytics.trackConversion(
  ///   'subscription_activated',
  ///   value: 49.90,
  ///   currency: 'BRL',
  ///   properties: {'plan_id': 'annual_pro'},
  /// );
  /// ```
  Future<void> trackConversion(
    String conversionName, {
    double? value,
    String? currency,
    Map<String, dynamic>? properties,
  }) {
    return trackEvent(
      conversionName,
      category: 'conversion',
      properties: {
        if (value != null) 'value': value,
        if (currency != null) 'currency': currency,
        if (properties != null) ...properties,
      },
    );
  }

  /// Track a completed purchase or payment transaction.
  Future<void> trackPurchaseCompleted({
    required String orderId,
    required double amount,
    String currency = 'USD',
    String? paymentMethod,
    List<Map<String, dynamic>>? items,
    Map<String, dynamic>? properties,
  }) {
    return trackConversion(
      'purchase_completed',
      value: amount,
      currency: currency,
      properties: {
        'order_id': orderId,
        if (paymentMethod != null) 'payment_method': paymentMethod,
        if (items != null) 'items': items,
        if (properties != null) ...properties,
      },
    );
  }

  // ---------------------------------------------------------------------------
  // Queue & Transmission Management
  // ---------------------------------------------------------------------------

  /// Enqueues an event and immediately triggers a flush attempt.
  void _enqueueEvent(Map<String, dynamic> eventPayload) {
    if (_eventQueue.length >= maxQueueSize) {
      _eventQueue.removeFirst(); // Drop oldest if queue reaches limit
    }
    _eventQueue.add(eventPayload);
    flush();
  }

  /// Flush pending queued events to the backend telemetry server.
  Future<void> flush() async {
    if (_isFlushing || _eventQueue.isEmpty) return;
    _isFlushing = true;

    try {
      // Drain up to 100 events from the queue for batch transmission
      final eventsToSend = <Map<String, dynamic>>[];
      while (_eventQueue.isNotEmpty && eventsToSend.length < 100) {
        eventsToSend.add(_eventQueue.removeFirst());
      }

      if (eventsToSend.isEmpty) {
        _isFlushing = false;
        return;
      }

      final success = eventsToSend.length == 1
          ? await _sendSingleEvent(eventsToSend.first)
          : await _sendBatchEvents(eventsToSend);

      if (!success) {
        // Re-insert unsent events at the front of the queue to retry later
        for (final item in eventsToSend.reversed) {
          if (_eventQueue.length < maxQueueSize) {
            _eventQueue.addFirst(item);
          }
        }
      }
    } catch (e) {
      debugPrint('[AnalyticsService] Unexpected error flushing telemetry: $e');
    } finally {
      _isFlushing = false;
    }
  }

  /// Send a single event to `POST /api/analytics/event`
  Future<bool> _sendSingleEvent(Map<String, dynamic> event) async {
    final uri = Uri.parse(_normalizeUrl(baseUrl, '/api/analytics/event'));
    try {
      final response = await _httpClient.post(
        uri,
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          if (defaultHeaders != null) ...defaultHeaders!,
        },
        body: jsonEncode(event),
      ).timeout(const Duration(seconds: 10));

      return response.statusCode >= 200 && response.statusCode < 300;
    } catch (e) {
      debugPrint('[AnalyticsService] Network failure sending single event: $e');
      return false;
    }
  }

  /// Send a batch of events to `POST /api/analytics/events/batch`
  Future<bool> _sendBatchEvents(List<Map<String, dynamic>> events) async {
    final uri = Uri.parse(_normalizeUrl(baseUrl, '/api/analytics/events/batch'));
    try {
      final response = await _httpClient.post(
        uri,
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          if (defaultHeaders != null) ...defaultHeaders!,
        },
        body: jsonEncode({'events': events}),
      ).timeout(const Duration(seconds: 15));

      return response.statusCode >= 200 && response.statusCode < 300;
    } catch (e) {
      debugPrint('[AnalyticsService] Network failure sending batch events: $e');
      return false;
    }
  }

  /// Start periodic flush timer
  void _startPeriodicFlush(Duration interval) {
    _flushTimer?.cancel();
    _flushTimer = Timer.periodic(interval, (_) => flush());
  }

  /// Detect runtime platform safely
  String _detectPlatform() {
    if (kIsWeb) return 'web';
    try {
      if (Platform.isAndroid) return 'android';
      if (Platform.isIOS) return 'ios';
      if (Platform.isMacOS) return 'macos';
      if (Platform.isWindows) return 'windows';
      if (Platform.isLinux) return 'linux';
      if (Platform.isFuchsia) return 'fuchsia';
    } catch (_) {
      return 'unknown';
    }
    return 'unknown';
  }

  /// Helper to normalize base URL and endpoint paths
  String _normalizeUrl(String base, String endpoint) {
    final cleanBase = base.endsWith('/') ? base.substring(0, base.length - 1) : base;
    final cleanEndpoint = endpoint.startsWith('/') ? endpoint : '/$endpoint';
    return '$cleanBase$cleanEndpoint';
  }

  /// Dispose resources and cancel background timers
  void dispose() {
    _flushTimer?.cancel();
    _httpClient.close();
  }
}
