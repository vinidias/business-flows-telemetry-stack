/*
===============================================================================
Model: mart_platform_split
Layer: Marts
Description: Segments telemetry interactions, active users, and business revenue
             across client platforms (iOS vs Android vs Web).
===============================================================================
*/

-- CTE 1: platform_events
-- Aggregates telemetry volume and active users per date and platform
WITH platform_events AS (
    SELECT
        event_date AS metric_date,
        platform,
        COUNT(event_id) AS events_count,
        COUNT(DISTINCT session_id) AS sessions_count,
        COUNT(DISTINCT user_id) AS active_users_count
    FROM {{ ref('stg_events') }}
    GROUP BY event_date, platform
),

-- CTE 2: platform_users_registered
-- Counts new signups segmented by initial registration platform
platform_users_registered AS (
    SELECT
        registration_date AS metric_date,
        platform,
        COUNT(DISTINCT user_id) AS registrations_count
    FROM {{ ref('stg_users') }}
    GROUP BY registration_date, platform
),

-- CTE 3: platform_transactions
-- Attaches transactions to platform based on user registration platform or event platform
platform_transactions AS (
    SELECT
        t.transaction_date AS metric_date,
        u.platform,
        COUNT(t.transaction_id) AS transactions_count,
        COALESCE(SUM(CASE WHEN t.is_successful = 1 THEN t.amount ELSE 0 END), 0.0) AS revenue_amount
    FROM {{ ref('stg_transactions') }} t
    LEFT JOIN {{ ref('stg_users') }} u ON t.user_id = u.user_id
    GROUP BY t.transaction_date, u.platform
),

-- CTE 4: calendar_platforms
-- Builds full grid of distinct dates and platforms
calendar_platforms AS (
    SELECT metric_date, platform FROM platform_events
    UNION
    SELECT metric_date, platform FROM platform_users_registered
    UNION
    SELECT metric_date, platform FROM platform_transactions
),

-- CTE 5: combined_platform_metrics
-- Joins all metrics and computes daily platform market share
combined_platform_metrics AS (
    SELECT
        cp.metric_date,
        cp.platform,
        COALESCE(pe.active_users_count, 0) AS active_users_count,
        COALESCE(pe.events_count, 0) AS events_count,
        COALESCE(pe.sessions_count, 0) AS sessions_count,
        COALESCE(pr.registrations_count, 0) AS registrations_count,
        COALESCE(pt.transactions_count, 0) AS transactions_count,
        COALESCE(pt.revenue_amount, 0.0) AS revenue_amount,
        
        -- Total daily events across all platforms for share percentage
        SUM(COALESCE(pe.events_count, 0)) OVER (
            PARTITION BY cp.metric_date
        ) AS daily_total_events_all_platforms
    FROM calendar_platforms cp
    LEFT JOIN platform_events pe 
      ON cp.metric_date = pe.metric_date AND cp.platform = pe.platform
    LEFT JOIN platform_users_registered pr 
      ON cp.metric_date = pr.metric_date AND cp.platform = pr.platform
    LEFT JOIN platform_transactions pt 
      ON cp.metric_date = pt.metric_date AND cp.platform = pt.platform
)

-- Final SELECT: Platform Breakdown Mart
SELECT
    metric_date,
    platform,
    active_users_count,
    events_count,
    sessions_count,
    registrations_count,
    transactions_count,
    revenue_amount,
    CASE
        WHEN daily_total_events_all_platforms > 0
        THEN ROUND(CAST(events_count AS DOUBLE) / CAST(daily_total_events_all_platforms AS DOUBLE), 4)
        ELSE 0.0
    END AS platform_event_share_ratio
FROM combined_platform_metrics
ORDER BY metric_date DESC, platform ASC
