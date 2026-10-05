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
        role,
        status,
        platform,
        country_code,
        professional_category_id,
        professional_category_name,
        registration_kind,
        registration_number_present,
        professional_fields_available,
        created_at,
        updated_at
    FROM {{ source('raw', 'raw_users') }}
),

-- CTE 2: standardized
-- Cleans nulls, casts timestamps, and normalizes categorical values
standardized AS (
    SELECT
        CAST(COALESCE(user_id, CAST(id AS VARCHAR)) AS VARCHAR) AS user_id,
        LOWER(COALESCE(role, 'customer')) AS user_role,
        CASE
            WHEN CAST(status AS VARCHAR) = '1' THEN 'active'
            WHEN CAST(status AS VARCHAR) = '0' THEN 'pending'
            ELSE LOWER(COALESCE(CAST(status AS VARCHAR), 'unknown'))
        END AS user_status,
        LOWER(COALESCE(platform, 'web')) AS platform,
        COALESCE(country_code, 'BR') AS country_code,
        CAST(professional_category_id AS VARCHAR) AS professional_category_id,
        COALESCE(professional_category_name, 'Não informada') AS professional_category_name,
        COALESCE(registration_kind, 'missing') AS registration_kind,
        COALESCE(registration_number_present, FALSE) AS registration_number_present,
        COALESCE(professional_fields_available, FALSE) AS professional_fields_available,
        CAST(created_at AS TIMESTAMP) AS created_at,
        CAST(COALESCE(updated_at, created_at) AS TIMESTAMP) AS updated_at,
        CAST(CAST(created_at AS DATE) AS DATE) AS registration_date
    FROM source_data
    WHERE id IS NOT NULL
)

-- Final SELECT: Returns cleaned and deduplicated user dimension
SELECT
    user_id,
    user_role,
    user_status,
    platform,
    country_code,
    professional_category_id,
    professional_category_name,
    registration_kind,
    registration_number_present,
    professional_fields_available,
    created_at,
    updated_at,
    registration_date
FROM standardized
