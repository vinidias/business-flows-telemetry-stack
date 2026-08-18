/*
===============================================================================
Model: mart_event_funnel
Layer: Marts
Description: Generic multi-step conversion funnel based on event_name telemetry.
             Measures total occurrences, unique users per step, step-to-step drop-off,
             and cumulative conversion rate from top of funnel.
===============================================================================
*/

-- CTE 1: event_ranks
-- Groups telemetry events and assigns standard funnel hierarchy order
WITH event_ranks AS (
    SELECT
        event_name,
        COUNT(event_id) AS total_events,
        COUNT(DISTINCT user_id) AS unique_users_count,
        COUNT(DISTINCT session_id) AS unique_sessions_count,
        MIN(created_at) AS first_event_seen_at,
        MAX(created_at) AS last_event_seen_at
    FROM {{ ref('stg_events') }}
    GROUP BY event_name
),

-- CTE 2: ordered_funnel_steps
-- Assigns step numbers based on user volumes or predefined canonical event names
ordered_funnel_steps AS (
    SELECT
        event_name,
        total_events,
        unique_users_count,
        unique_sessions_count,
        first_event_seen_at,
        last_event_seen_at,
        DENSE_RANK() OVER (ORDER BY unique_users_count DESC, total_events DESC) AS funnel_step_order,
        CONCAT('Step ', CAST(DENSE_RANK() OVER (ORDER BY unique_users_count DESC, total_events DESC) AS VARCHAR), ': ', event_name) AS step_name
    FROM event_ranks
),

-- CTE 3: funnel_conversion_calculations
-- Calculates step-over-step conversion rate and top-of-funnel conversion rate
funnel_conversion_calculations AS (
    SELECT
        funnel_step_order,
        step_name,
        event_name,
        total_events,
        unique_users_count,
        unique_sessions_count,
        
        -- Top of funnel base volume (Step 1 unique users)
        FIRST_VALUE(unique_users_count) OVER (
            ORDER BY funnel_step_order ASC
        ) AS top_of_funnel_users,
        
        -- Previous step unique users for step conversion
        LAG(unique_users_count) OVER (
            ORDER BY funnel_step_order ASC
        ) AS previous_step_users
    FROM ordered_funnel_steps
),

-- CTE 4: final_metrics
-- Computes final conversion percentages
final_metrics AS (
    SELECT
        funnel_step_order,
        step_name,
        event_name,
        total_events,
        unique_users_count,
        unique_sessions_count,
        
        -- Conversion from previous step (Step Conversion Rate)
        CASE
            WHEN previous_step_users IS NULL OR previous_step_users = 0 THEN 1.0
            ELSE ROUND(CAST(unique_users_count AS DOUBLE) / CAST(previous_step_users AS DOUBLE), 4)
        END AS step_conversion_rate,
        
        -- Conversion from top of funnel (Overall Conversion Rate)
        CASE
            WHEN top_of_funnel_users IS NULL OR top_of_funnel_users = 0 THEN 1.0
            ELSE ROUND(CAST(unique_users_count AS DOUBLE) / CAST(top_of_funnel_users AS DOUBLE), 4)
        END AS overall_conversion_rate,
        
        -- Drop-off count from previous step
        CASE
            WHEN previous_step_users IS NULL THEN 0
            ELSE GREATEST(previous_step_users - unique_users_count, 0)
        END AS step_dropoff_users_count
    FROM funnel_conversion_calculations
)

-- Final SELECT: Generic Event Funnel
SELECT
    funnel_step_order,
    step_name,
    event_name,
    total_events,
    unique_users_count,
    unique_sessions_count,
    step_conversion_rate,
    overall_conversion_rate,
    step_dropoff_users_count
FROM final_metrics
ORDER BY funnel_step_order ASC
