/*
===============================================================================
Model: int_user_journey
Layer: Intermediate
Description: Aggregates user lifetime activity across events and transactions
             to build a complete user lifecycle and journey profile.
===============================================================================
*/

-- CTE 1: users_base
-- Reads standardized user records
WITH users_base AS (
    SELECT
        user_id,
        email,
        user_role,
        user_status,
        platform AS registration_platform,
        country_code,
        created_at AS registered_at,
        registration_date
    FROM {{ ref('stg_users') }}
),

-- CTE 2: user_events_summary
-- Computes first event, last active event, and total telemetry interactions per user
user_events_summary AS (
    SELECT
        user_id,
        MIN(created_at) AS first_event_at,
        MAX(created_at) AS last_event_at,
        MIN(event_date) AS first_event_date,
        MAX(event_date) AS last_event_date,
        COUNT(event_id) AS total_events_count,
        COUNT(DISTINCT event_date) AS total_active_days,
        COUNT(DISTINCT session_id) AS total_sessions_count
    FROM {{ ref('stg_events') }}
    WHERE user_id IS NOT NULL
    GROUP BY user_id
),

-- CTE 3: user_transactions_summary
-- Computes lifetime transaction metrics (total spend, success count, first/last purchase)
user_transactions_summary AS (
    SELECT
        user_id,
        MIN(created_at) AS first_transaction_at,
        MAX(created_at) AS last_transaction_at,
        MIN(transaction_date) AS first_transaction_date,
        MAX(transaction_date) AS last_transaction_date,
        COUNT(transaction_id) AS total_transactions_count,
        SUM(is_successful) AS successful_transactions_count,
        COALESCE(SUM(CASE WHEN is_successful = 1 THEN amount ELSE 0 END), 0.0) AS lifetime_value_amount
    FROM {{ ref('stg_transactions') }}
    WHERE user_id IS NOT NULL
    GROUP BY user_id
),

-- CTE 4: joined_journey
-- Joins user base with summarized events and transaction history
joined_journey AS (
    SELECT
        u.user_id,
        u.email,
        u.user_role,
        u.user_status,
        u.registration_platform,
        u.country_code,
        u.registered_at,
        u.registration_date,
        
        -- Event Telemetry metrics
        COALESCE(e.total_events_count, 0) AS total_events_count,
        COALESCE(e.total_active_days, 0) AS total_active_days,
        COALESCE(e.total_sessions_count, 0) AS total_sessions_count,
        e.first_event_at,
        e.last_event_at,
        e.first_event_date,
        e.last_event_date,
        
        -- Transaction metrics
        COALESCE(t.total_transactions_count, 0) AS total_transactions_count,
        COALESCE(t.successful_transactions_count, 0) AS successful_transactions_count,
        COALESCE(t.lifetime_value_amount, 0.0) AS lifetime_value_amount,
        t.first_transaction_at,
        t.last_transaction_at,
        t.first_transaction_date,
        t.last_transaction_date,
        
        -- Funnel & Conversion flags
        CASE WHEN e.first_event_at IS NOT NULL THEN 1 ELSE 0 END AS has_performed_event,
        CASE WHEN t.successful_transactions_count > 0 THEN 1 ELSE 0 END AS has_converted_paying,
        
        -- Time-to-convert metrics (in days)
        CASE 
            WHEN t.first_transaction_date IS NOT NULL 
            THEN CAST(t.first_transaction_date - u.registration_date AS INTEGER)
            ELSE NULL 
        END AS days_to_first_transaction
    FROM users_base u
    LEFT JOIN user_events_summary e ON u.user_id = e.user_id
    LEFT JOIN user_transactions_summary t ON u.user_id = t.user_id
)

-- Final SELECT: User journey summary
SELECT
    user_id,
    email,
    user_role,
    user_status,
    registration_platform,
    country_code,
    registered_at,
    registration_date,
    total_events_count,
    total_active_days,
    total_sessions_count,
    first_event_at,
    last_event_at,
    first_event_date,
    last_event_date,
    total_transactions_count,
    successful_transactions_count,
    lifetime_value_amount,
    first_transaction_at,
    last_transaction_at,
    first_transaction_date,
    last_transaction_date,
    has_performed_event,
    has_converted_paying,
    days_to_first_transaction
FROM joined_journey
