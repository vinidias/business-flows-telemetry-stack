-- One row per registration date, professional area, and current account status.
-- The source contains classifications only; professional registration numbers
-- are discarded by the extractor before Parquet or DuckDB persistence.
SELECT
    registration_date AS metric_date,
    COALESCE(professional_category_id, 'unknown') AS professional_category_id,
    professional_category_name,
    user_status,
    COUNT(DISTINCT user_id) AS registrations_count,
    COUNT(DISTINCT CASE WHEN registration_kind = 'crm' THEN user_id END) AS crm_informed_count,
    COUNT(DISTINCT CASE WHEN registration_kind = 'other' THEN user_id END) AS other_registration_count,
    COUNT(DISTINCT CASE WHEN registration_kind = 'missing' THEN user_id END) AS registration_missing_count
FROM {{ ref('stg_users') }}
WHERE user_role IN ('provider', 'consultant')
  AND professional_fields_available = TRUE
GROUP BY 1, 2, 3, 4
