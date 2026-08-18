# Flutter Analytics Service (Plug-and-Play)

A lightweight, zero-bloat telemetry client for Flutter applications that communicates directly with your `business-flows-telemetry-stack` backend (Laravel, Django, or FastAPI).

---

## 🚀 Key Features

- **Zero heavy SDKs**: Uses only the official `http` Dart package (no Firebase or Google Play Services required).
- **Offline Resiliency**: In-memory event queue with automatic retry upon network failure.
- **Auto Platform Detection**: Automatically flags events as `android`, `ios`, `web`, `macos`, `windows`, `linux`.
- **Pre-built helpers**: Ready-to-use methods for screen views, button interactions, business conversions, and e-commerce transactions.
- **Configurable**: Base URL and custom headers configured via constructor.

---

## 📦 1. Installation

Add the `http` package to your `pubspec.yaml`:

```yaml
dependencies:
  flutter:
    sdk: flutter
  http: ^1.2.0
```

Then copy `analytics_service.dart` into your project (e.g. `lib/services/analytics_service.dart`).

---

## 🛠️ 2. Quick Start

### Initialize in `main.dart`

```dart
import 'package:flutter/material.dart';
import 'services/analytics_service.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();

  // Initialize global analytics singleton
  AnalyticsService.initialize(
    baseUrl: 'https://api.yourdomain.com', // or 'http://10.0.2.2:8000' for Android Emulator
    appVersion: '1.0.0',
    flushInterval: const Duration(seconds: 20),
  );

  // Track app launch
  AnalyticsService.instance.trackAppOpen();

  runApp(const MyApp());
}
```

---

## 💡 3. Usage Examples

### Identify Authenticated User

Call `setUserId` upon successful login and `setUserId(null)` on logout:

```dart
// After login:
AnalyticsService.instance.setUserId('usr_12345');
AnalyticsService.instance.setGlobalProperties({
  'plan': 'premium',
  'account_type': 'business',
});

// After logout:
AnalyticsService.instance.setUserId(null);
AnalyticsService.instance.clearGlobalProperties();
```

---

### Track Screen Views

```dart
// Track screen view manually in initState or build
AnalyticsService.instance.trackScreen(
  'ProductDetailScreen',
  properties: {
    'product_id': 'prod_99',
    'category': 'machinery',
  },
);
```

---

### Track Button Taps & User Actions

```dart
ElevatedButton(
  onPressed: () {
    AnalyticsService.instance.trackButtonTap(
      'request_quote_btn',
      screenName: 'ProductDetailScreen',
      properties: {'item_id': 99},
    );
    // Perform action...
  },
  child: const Text('Request Quote'),
)
```

---

### Track Business Conversions & Purchases

```dart
// Track conversion
AnalyticsService.instance.trackConversion(
  'lead_form_submitted',
  properties: {
    'form_type': 'contact_sales',
    'source': 'landing_page_hero',
  },
);

// Track purchase
AnalyticsService.instance.trackPurchaseCompleted(
  orderId: 'ORD-987654',
  amount: 249.90,
  currency: 'BRL',
  paymentMethod: 'credit_card',
  items: [
    {'sku': 'PLAN-PRO-YEAR', 'price': 249.90, 'quantity': 1}
  ],
);
```

---

## 🔄 4. Custom Events

```dart
AnalyticsService.instance.trackEvent(
  'file_exported',
  category: 'productivity',
  properties: {
    'format': 'pdf',
    'total_pages': 14,
    'execution_ms': 320,
  },
);
```

---

## 🧪 5. Testing & Dependency Injection

You can instantiate `AnalyticsService` directly without the singleton for unit testing with mocked `http.Client`:

```dart
final mockHttpClient = MockHttpClient();
final analytics = AnalyticsService(
  baseUrl: 'http://localhost:8000',
  httpClient: mockHttpClient,
);
```
