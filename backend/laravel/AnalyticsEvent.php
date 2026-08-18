<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Builder;
use Carbon\Carbon;

/**
 * Class AnalyticsEvent
 * 
 * Generic telemetry and business flow analytics event model.
 * Stores telemetry data from mobile applications, web frontends, and API consumers.
 *
 * @package App\Models
 * @property int $id
 * @property string $event_name
 * @property string|null $event_category
 * @property string|null $user_id
 * @property string|null $session_id
 * @property string|null $platform
 * @property string|null $app_version
 * @property string|null $os_version
 * @property string|null $device_model
 * @property array|null $properties
 * @property string|null $ip_address
 * @property string|null $user_agent
 * @property Carbon $occurred_at
 * @property Carbon $created_at
 * @property Carbon $updated_at
 */
class AnalyticsEvent extends Model
{
    use HasFactory;

    /**
     * The table associated with the model.
     *
     * @var string
     */
    protected $table = 'analytics_events';

    /**
     * The attributes that are mass assignable.
     *
     * @var array<int, string>
     */
    protected $fillable = [
        'event_name',
        'event_category',
        'user_id',
        'session_id',
        'platform',
        'app_version',
        'os_version',
        'device_model',
        'properties',
        'ip_address',
        'user_agent',
        'occurred_at',
    ];

    /**
     * The attributes that should be cast.
     *
     * @var array<string, string>
     */
    protected $casts = [
        'properties' => 'array',
        'occurred_at' => 'datetime',
    ];

    /**
     * Scope a query to only include events with a specific name.
     */
    public function scopeByName(Builder $query, string $eventName): Builder
    {
        return $query->where('event_name', $eventName);
    }

    /**
     * Scope a query to filter events by category (e.g., 'navigation', 'ecommerce', 'auth').
     */
    public function scopeByCategory(Builder $query, string $category): Builder
    {
        return $query->where('event_category', $category);
    }

    /**
     * Scope a query to filter events by authenticated user ID.
     */
    public function scopeForUser(Builder $query, string|int $userId): Builder
    {
        return $query->where('user_id', (string) $userId);
    }

    /**
     * Scope a query to filter events within a specific time range.
     */
    public function scopeInTimeRange(Builder $query, Carbon|string $start, Carbon|string $end): Builder
    {
        return $query->whereBetween('occurred_at', [$start, $end]);
    }

    /**
     * Scope a query to filter events by target platform ('android', 'ios', 'web').
     */
    public function scopeByPlatform(Builder $query, string $platform): Builder
    {
        return $query->where('platform', strtolower($platform));
    }
}
