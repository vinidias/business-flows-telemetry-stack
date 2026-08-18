<?php

namespace App\Http\Controllers;

use App\Models\AnalyticsEvent;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Validator;

/**
 * Class AnalyticsController
 * 
 * Generic API Controller responsible for receiving and querying telemetry events.
 * Accepts single and batched events from mobile and web clients.
 *
 * @package App\Http\Controllers
 */
class AnalyticsController extends Controller
{
    /**
     * Ingest a single analytics event.
     * Endpoint: POST /api/analytics/event
     *
     * @param Request $request
     * @return JsonResponse
     */
    public function store(Request $request): JsonResponse
    {
        $validator = Validator::make($request->all(), [
            'event_name'     => 'required|string|max:255',
            'event_category' => 'nullable|string|max:100',
            'user_id'        => 'nullable|string|max:255',
            'session_id'     => 'nullable|string|max:255',
            'platform'       => 'nullable|string|max:50',
            'app_version'    => 'nullable|string|max:50',
            'os_version'     => 'nullable|string|max:50',
            'device_model'   => 'nullable|string|max:100',
            'properties'     => 'nullable|array',
            'occurred_at'    => 'nullable|date',
        ]);

        if ($validator->fails()) {
            return response()->json([
                'success' => false,
                'message' => 'Validation error.',
                'errors'  => $validator->errors(),
            ], 422);
        }

        try {
            $data = $validator->validated();

            // Auto-detect user_id from auth token if not explicitly provided in payload
            if (empty($data['user_id']) && $request->user()) {
                $data['user_id'] = (string) $request->user()->id;
            }

            // Capture network and client environment
            $data['ip_address'] = $request->ip();
            $data['user_agent'] = $request->userAgent();

            // Fallback occurred_at to current timestamp if missing
            if (empty($data['occurred_at'])) {
                $data['occurred_at'] = Carbon::now();
            }

            $event = AnalyticsEvent::create($data);

            return response()->json([
                'success' => true,
                'message' => 'Event tracked successfully.',
                'event_id' => $event->id,
            ], 201);
        } catch (\Throwable $e) {
            Log::error('[AnalyticsController] Failed to record analytics event: ' . $e->getMessage(), [
                'exception' => $e,
                'payload'   => $request->all(),
            ]);

            return response()->json([
                'success' => false,
                'message' => 'Internal server error recording event.',
            ], 500);
        }
    }

    /**
     * Ingest a batch of analytics events.
     * Endpoint: POST /api/analytics/events/batch
     *
     * @param Request $request
     * @return JsonResponse
     */
    public function storeBatch(Request $request): JsonResponse
    {
        $validator = Validator::make($request->all(), [
            'events'                  => 'required|array|min:1|max:500',
            'events.*.event_name'     => 'required|string|max:255',
            'events.*.event_category' => 'nullable|string|max:100',
            'events.*.user_id'        => 'nullable|string|max:255',
            'events.*.session_id'     => 'nullable|string|max:255',
            'events.*.platform'       => 'nullable|string|max:50',
            'events.*.app_version'    => 'nullable|string|max:50',
            'events.*.os_version'     => 'nullable|string|max:50',
            'events.*.device_model'   => 'nullable|string|max:100',
            'events.*.properties'     => 'nullable|array',
            'events.*.occurred_at'    => 'nullable|date',
        ]);

        if ($validator->fails()) {
            return response()->json([
                'success' => false,
                'message' => 'Batch validation error.',
                'errors'  => $validator->errors(),
            ], 422);
        }

        try {
            $events = $validator->validated()['events'];
            $authUserId = $request->user()?->id ? (string) $request->user()->id : null;
            $ip = $request->ip();
            $userAgent = $request->userAgent();
            $now = Carbon::now();

            $insertPayload = [];
            foreach ($events as $item) {
                $insertPayload[] = [
                    'event_name'     => $item['event_name'],
                    'event_category' => $item['event_category'] ?? null,
                    'user_id'        => $item['user_id'] ?? $authUserId,
                    'session_id'     => $item['session_id'] ?? null,
                    'platform'       => $item['platform'] ?? null,
                    'app_version'    => $item['app_version'] ?? null,
                    'os_version'     => $item['os_version'] ?? null,
                    'device_model'   => $item['device_model'] ?? null,
                    'properties'     => isset($item['properties']) ? json_encode($item['properties']) : null,
                    'ip_address'     => $ip,
                    'user_agent'     => $userAgent,
                    'occurred_at'    => !empty($item['occurred_at']) ? Carbon::parse($item['occurred_at']) : $now,
                    'created_at'     => $now,
                    'updated_at'     => $now,
                ];
            }

            AnalyticsEvent::insert($insertPayload);

            return response()->json([
                'success'       => true,
                'message'       => 'Batch events tracked successfully.',
                'events_count'  => count($insertPayload),
            ], 201);
        } catch (\Throwable $e) {
            Log::error('[AnalyticsController] Batch insertion failed: ' . $e->getMessage(), [
                'exception' => $e,
            ]);

            return response()->json([
                'success' => false,
                'message' => 'Internal server error processing event batch.',
            ], 500);
        }
    }

    /**
     * Retrieve aggregated telemetry metrics.
     * Endpoint: GET /api/analytics/metrics
     *
     * @param Request $request
     * @return JsonResponse
     */
    public function metrics(Request $request): JsonResponse
    {
        $days = (int) $request->query('days', 30);
        $since = Carbon::now()->subDays($days);

        $totalEvents = AnalyticsEvent::where('occurred_at', '>=', $since)->count();
        $uniqueUsers = AnalyticsEvent::where('occurred_at', '>=', $since)
            ->whereNotNull('user_id')
            ->distinct('user_id')
            ->count('user_id');

        $topEvents = AnalyticsEvent::where('occurred_at', '>=', $since)
            ->selectRaw('event_name, count(*) as total')
            ->groupBy('event_name')
            ->orderByDesc('total')
            ->limit(10)
            ->get();

        $platformBreakdown = AnalyticsEvent::where('occurred_at', '>=', $since)
            ->selectRaw('platform, count(*) as total')
            ->groupBy('platform')
            ->orderByDesc('total')
            ->get();

        return response()->json([
            'success' => true,
            'period_days' => $days,
            'total_events' => $totalEvents,
            'unique_users' => $uniqueUsers,
            'top_events' => $topEvents,
            'platforms' => $platformBreakdown,
        ]);
    }
}
