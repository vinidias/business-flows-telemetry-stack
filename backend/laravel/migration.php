<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

/**
 * Migration for creating the analytics_events table.
 * 
 * Includes optimized indices for fast querying by event name, user,
 * platform, and timestamp ranges.
 */
return new class extends Migration
{
    /**
     * Run the migrations.
     */
    public function up(): void
    {
        Schema::create('analytics_events', function (Blueprint $table) {
            $table->id();

            // Core event identification
            $table->string('event_name', 255)->index();
            $table->string('event_category', 100)->nullable()->index();

            // Actor & Session identification
            $table->string('user_id', 255)->nullable()->index();
            $table->string('session_id', 255)->nullable()->index();

            // Device & Platform telemetry
            $table->string('platform', 50)->nullable()->index(); // e.g. 'android', 'ios', 'web'
            $table->string('app_version', 50)->nullable();
            $table->string('os_version', 50)->nullable();
            $table->string('device_model', 100)->nullable();

            // Arbitrary contextual JSON payload
            $table->json('properties')->nullable();

            // Network telemetry
            $table->ipAddress('ip_address')->nullable();
            $table->text('user_agent')->nullable();

            // Timing telemetry
            $table->timestamp('occurred_at')->index();
            $table->timestamps();

            // Composite indexes for fast analytical aggregation
            $table->index(['event_name', 'occurred_at']);
            $table->index(['user_id', 'occurred_at']);
            $table->index(['platform', 'occurred_at']);
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('analytics_events');
    }
};
