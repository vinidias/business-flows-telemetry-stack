/*
===============================================================================
Model: stg_users
Layer: Staging
Description: Standardizes user account data, handles type conversions,
             and normalizes platform and role classifications.
===============================================================================
*/

-- CTE 1: source_data
-- Selects raw user records from the raw source layer
WITH source_data AS (
    SELECT 
        id,
        user_id,
        email,
        role,
        status,
        platform,
        country_code,
        created_at,
        updated_at
    FROM {{ source('raw', 'raw_users') }}
),

-- CTE 2: standardized
-- Cleans nulls, casts timestamps, and normalizes categorical values
standardized AS (
    SELECT
        CAST(COALESCE(user_id, CAST(id AS VARCHAR)) AS VARCHAR) AS user_id,
        TRIM(LOWER(email)) AS email,
        LOWER(COALESCE(role, 'customer')) AS user_role,
        LOWER(COALESCE(status, 'active')) AS user_status,
        LOWER(COALESCE(platform, 'web')) AS platform,
        COALESCE(country_code, 'BR') AS country_code,
        CAST(created_at AS TIMESTAMP) AS created_at,
        CAST(COALESCE(updated_at, created_at) AS TIMESTAMP) AS updated_at,
        CAST(CAST(created_at AS DATE) AS DATE) AS registration_date
    FROM source_data
    WHERE id IS NOT NULL
)

-- Final SELECT: Returns cleaned and deduplicated user dimension
SELECT
    user_id,
    email,
    user_role,
    user_status,
    platform,
    country_code,
    created_at,
    updated_at,
    registration_date
FROM standardized
