/*
===============================================================================
Model: stg_events
Layer: Staging
Description: Cleans, parses, and normalizes product interaction telemetry
             events extracted from the analytics_events source table.
===============================================================================
*/

-- CTE 1: source_data
-- Ingests raw telemetry events from DuckDB raw source table
WITH source_data AS (
    SELECT 
        id,
        user_id,
        session_id,
        event_name,
        event_category,
        platform,
        app_version,
        properties_json,
        created_at
    FROM {{ source('raw', 'raw_analytics_events') }}
),

-- CTE 2: cleaned_events
-- Standardizes casing, normalizes platforms, and cleans timestamp fields
cleaned_events AS (
    SELECT
        CAST(id AS VARCHAR) AS event_id,
        CAST(user_id AS VARCHAR) AS user_id,
        CAST(COALESCE(session_id, 'unknown_session') AS VARCHAR) AS session_id,
        LOWER(TRIM(event_name)) AS event_name,
        LOWER(COALESCE(event_category, 'general')) AS event_category,
        CASE
            WHEN LOWER(platform) LIKE '%ios%' THEN 'ios'
            WHEN LOWER(platform) LIKE '%android%' THEN 'android'
            WHEN LOWER(platform) LIKE '%web%' THEN 'web'
            ELSE 'web'
        END AS platform,
        COALESCE(app_version, '1.0.0') AS app_version,
        properties_json,
        CAST(created_at AS TIMESTAMP) AS created_at,
        CAST(CAST(created_at AS DATE) AS DATE) AS event_date
    FROM source_data
    WHERE id IS NOT NULL
      AND event_name IS NOT NULL
)

-- Final SELECT: Filtered and validated telemetry event stream
SELECT
    event_id,
    user_id,
    session_id,
    event_name,
    event_category,
    platform,
    app_version,
    properties_json,
    created_at,
    event_date
FROM cleaned_events
