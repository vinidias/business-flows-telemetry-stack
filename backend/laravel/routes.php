<?php

use Illuminate\Support\Facades\Route;
use App\Http\Controllers\AnalyticsController;

/*
|--------------------------------------------------------------------------
| Analytics API Routes
|--------------------------------------------------------------------------
|
| These routes handle telemetry ingestion and metrics retrieval.
| You can paste this snippet into your `routes/api.php` file.
|
*/

Route::prefix('analytics')->group(function () {
    
    // Ingest single event (supports both guest and authenticated users)
    // Rate limited to prevent telemetry abuse (e.g., 120 requests/minute)
    Route::middleware(['throttle:120,1'])->group(function () {
        Route::post('/event', [AnalyticsController::class, 'store']);
        Route::post('/events/batch', [AnalyticsController::class, 'storeBatch']);
    });

    // Telemetry dashboard / metrics query endpoint
    // Optional: Protect with authentication / admin middleware in production
    Route::get('/metrics', [AnalyticsController::class, 'metrics']);
    
    // Example: Optional authenticated route group using Laravel Sanctum
    /*
    Route::middleware('auth:sanctum')->group(function () {
        Route::get('/user-journey', [AnalyticsController::class, 'userJourney']);
    });
    */
});
