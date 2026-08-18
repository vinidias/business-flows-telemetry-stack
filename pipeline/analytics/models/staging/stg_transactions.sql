/*
===============================================================================
Model: stg_transactions
Layer: Staging
Description: Standardizes financial transactions, booking payments,
             and monetary interactions.
===============================================================================
*/

-- CTE 1: source_data
-- Ingests raw transaction and payment records from the raw source
WITH source_data AS (
    SELECT 
        id,
        user_id,
        amount,
        currency,
        status,
        payment_method,
        created_at,
        updated_at
    FROM {{ source('raw', 'raw_transactions') }}
),

-- CTE 2: standardized_transactions
-- Cleans numerical amounts, standardizes transaction status and payment methods
standardized_transactions AS (
    SELECT
        CAST(id AS VARCHAR) AS transaction_id,
        CAST(user_id AS VARCHAR) AS user_id,
        CAST(COALESCE(amount, 0.0) AS DECIMAL(12, 2)) AS amount,
        UPPER(COALESCE(currency, 'BRL')) AS currency,
        LOWER(COALESCE(status, 'completed')) AS status,
        LOWER(COALESCE(payment_method, 'unknown')) AS payment_method,
        CAST(created_at AS TIMESTAMP) AS created_at,
        CAST(COALESCE(updated_at, created_at) AS TIMESTAMP) AS updated_at,
        CAST(CAST(created_at AS DATE) AS DATE) AS transaction_date,
        CASE
            WHEN LOWER(status) IN ('completed', 'success', 'paid', 'approved') THEN 1
            ELSE 0
        END AS is_successful
    FROM source_data
    WHERE id IS NOT NULL
)

-- Final SELECT: Verified financial transactions stream
SELECT
    transaction_id,
    user_id,
    amount,
    currency,
    status,
    payment_method,
    created_at,
    updated_at,
    transaction_date,
    is_successful
FROM standardized_transactions
