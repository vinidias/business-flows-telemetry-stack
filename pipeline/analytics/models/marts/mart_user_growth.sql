/*
===============================================================================
Model: mart_user_growth
Layer: Marts
Description: Computes daily user growth, DAU (Daily Active Users),
             WAU (Weekly Active Users), MAU (Monthly Active Users),
             new user registrations, and platform stickiness (DAU/MAU).
===============================================================================
*/

-- CTE 1: calendar_dates
-- Extracts distinct calendar dates across registrations and events
WITH calendar_dates AS (
    SELECT registration_date AS metric_date FROM {{ ref('stg_users') }}
    UNION
    SELECT event_date AS metric_date FROM {{ ref('stg_events') }}
),

-- CTE 2: daily_new_users
-- Counts new user registrations per calendar date
daily_new_users AS (
    SELECT
        registration_date AS metric_date,
        COUNT(DISTINCT user_id) AS new_registrations_count
    FROM {{ ref('stg_users') }}
    GROUP BY registration_date
),

-- CTE 3: daily_active_users
-- Computes distinct active users per calendar date (DAU)
daily_active_users AS (
    SELECT
        event_date AS metric_date,
        COUNT(DISTINCT user_id) AS dau_count
    FROM {{ ref('stg_events') }}
    GROUP BY event_date
),

-- CTE 4: daily_user_activity
-- Base user-date pairs for rolling window active calculations
daily_user_activity AS (
    SELECT DISTINCT
        event_date,
        user_id
    FROM {{ ref('stg_events') }}
),

-- CTE 5: rolling_activity
-- Computes rolling 7-day (WAU) and 30-day (MAU) active user counts
rolling_activity AS (
    SELECT
        c.metric_date,
        COUNT(DISTINCT CASE 
            WHEN a.event_date BETWEEN c.metric_date - INTERVAL '6 DAY' AND c.metric_date 
            THEN a.user_id 
        END) AS wau_count,
        COUNT(DISTINCT CASE 
            WHEN a.event_date BETWEEN c.metric_date - INTERVAL '29 DAY' AND c.metric_date 
            THEN a.user_id 
        END) AS mau_count
    FROM calendar_dates c
    LEFT JOIN daily_user_activity a 
      ON a.event_date BETWEEN c.metric_date - INTERVAL '29 DAY' AND c.metric_date
    GROUP BY c.metric_date
),

-- CTE 6: aggregated_growth
-- Combines new users, DAU, WAU, MAU, and cumulative user totals
aggregated_growth AS (
    SELECT
        c.metric_date,
        COALESCE(d.dau_count, 0) AS dau_count,
        COALESCE(r.wau_count, 0) AS wau_count,
        COALESCE(r.mau_count, 0) AS mau_count,
        COALESCE(u.new_registrations_count, 0) AS new_registrations_count,
        SUM(COALESCE(u.new_registrations_count, 0)) OVER (
            ORDER BY c.metric_date 
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS cumulative_total_users,
        CASE
            WHEN COALESCE(r.mau_count, 0) > 0 
            THEN ROUND(CAST(COALESCE(d.dau_count, 0) AS DOUBLE) / CAST(r.mau_count AS DOUBLE), 4)
            ELSE 0.0
        END AS dau_to_mau_stickiness_ratio
    FROM calendar_dates c
    LEFT JOIN daily_new_users u ON c.metric_date = u.metric_date
    LEFT JOIN daily_active_users d ON c.metric_date = d.metric_date
    LEFT JOIN rolling_activity r ON c.metric_date = r.metric_date
)

-- Final SELECT: User growth mart
SELECT
    metric_date,
    dau_count,
    wau_count,
    mau_count,
    new_registrations_count,
    cumulative_total_users,
    dau_to_mau_stickiness_ratio
FROM aggregated_growth
ORDER BY metric_date ASC
