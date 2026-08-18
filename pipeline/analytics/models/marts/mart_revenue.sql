/*
===============================================================================
Model: mart_revenue
Layer: Marts
Description: Computes daily and cumulative revenue performance, transaction
             counts, successful checkout volume, and Average Order Value (AOV)
             segmented by currency and payment method.
===============================================================================
*/

-- CTE 1: daily_transactions_base
-- Extracts daily transactions filtered for successful orders
WITH daily_transactions_base AS (
    SELECT
        transaction_date AS metric_date,
        currency,
        payment_method,
        transaction_id,
        user_id,
        amount,
        is_successful
    FROM {{ ref('stg_transactions') }}
),

-- CTE 2: daily_revenue_aggregated
-- Aggregates transaction count, revenue amount, and paying customers by date and method
daily_revenue_aggregated AS (
    SELECT
        metric_date,
        currency,
        payment_method,
        COUNT(transaction_id) AS total_transactions_count,
        SUM(is_successful) AS daily_successful_transactions,
        SUM(CASE WHEN is_successful = 0 THEN 1 ELSE 0 END) AS daily_failed_transactions,
        COUNT(DISTINCT CASE WHEN is_successful = 1 THEN user_id END) AS daily_paying_users_count,
        COALESCE(SUM(CASE WHEN is_successful = 1 THEN amount ELSE 0 END), 0.0) AS daily_gross_revenue
    FROM daily_transactions_base
    GROUP BY metric_date, currency, payment_method
),

-- CTE 3: revenue_metrics
-- Adds Average Order Value (AOV) and cumulative running revenue
revenue_metrics AS (
    SELECT
        metric_date,
        currency,
        payment_method,
        total_transactions_count,
        daily_successful_transactions,
        daily_failed_transactions,
        daily_paying_users_count,
        daily_gross_revenue,
        
        -- Daily Average Order Value (AOV)
        CASE
            WHEN daily_successful_transactions > 0 
            THEN ROUND(CAST(daily_gross_revenue AS DOUBLE) / CAST(daily_successful_transactions AS DOUBLE), 2)
            ELSE 0.0
        END AS daily_average_order_value,
        
        -- Cumulative Gross Revenue per currency and payment method
        SUM(daily_gross_revenue) OVER (
            PARTITION BY currency, payment_method
            ORDER BY metric_date
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS cumulative_total_revenue
    FROM daily_revenue_aggregated
)

-- Final SELECT: Revenue performance mart
SELECT
    metric_date,
    currency,
    payment_method,
    total_transactions_count,
    daily_successful_transactions,
    daily_failed_transactions,
    daily_paying_users_count,
    daily_gross_revenue,
    daily_average_order_value,
    cumulative_total_revenue
FROM revenue_metrics
ORDER BY metric_date DESC, currency, payment_method
