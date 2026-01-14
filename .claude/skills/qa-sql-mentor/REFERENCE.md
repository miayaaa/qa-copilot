# Snowflake SQL Quick Reference

## QA Pattern Shortcuts

| Check | Pattern |
|-------|---------|
| Duplicates | `GROUP BY key HAVING COUNT(*) > 1` |
| NULL % | `100.0 * (COUNT(*) - COUNT(col)) / COUNT(*)` |
| Time order | `WHERE end_ts < start_ts` |
| Balance mismatch | `WHERE ABS(recorded - calculated) > 0.01` |

## Table Type Templates

### SCD2 Dimension Tables
```sql
-- Row count (current records only)
SELECT COUNT(*) FROM {TABLE} WHERE CURRENT_RECORD_IND = 1;

-- SCD2 version distribution (verify history migrated)
SELECT CURRENT_RECORD_IND, COUNT(*) AS cnt
FROM {TABLE}
GROUP BY CURRENT_RECORD_IND;

-- Grain uniqueness on current records
SELECT {GRAIN_COLS}, COUNT(*) AS cnt
FROM {TABLE}
WHERE CURRENT_RECORD_IND = 1
GROUP BY {GRAIN_COLS}
HAVING COUNT(*) > 1;
```

### Snapshot Tables
```sql
-- Row count for specific date
SELECT COUNT(*) FROM {TABLE} WHERE SNAPSHOT_DATE = '{DATE}';

-- Date boundary check
SELECT MIN(SNAPSHOT_DATE), MAX(SNAPSHOT_DATE) FROM {TABLE};

-- Balance SUM for specific date
SELECT SUM({BALANCE_COL}) FROM {TABLE} WHERE SNAPSHOT_DATE = '{DATE}';
```

### Event Tables
```sql
-- Row count for date range
SELECT COUNT(*) FROM {TABLE}
WHERE EVENT_TIMESTAMP BETWEEN '{START}' AND '{END}';

-- Event type distribution
SELECT EVENT_TYPE, COUNT(*) AS cnt
FROM {TABLE}
WHERE EVENT_TIMESTAMP BETWEEN '{START}' AND '{END}'
GROUP BY EVENT_TYPE
ORDER BY cnt DESC;

-- Time boundary check
SELECT MIN(EVENT_TIMESTAMP), MAX(EVENT_TIMESTAMP) FROM {TABLE};
```

### Monthly Fact Tables
```sql
-- Row count for month
SELECT COUNT(*) FROM {TABLE} WHERE D_DATE_KEY = '{MONTH}';

-- Key metrics SUM for month
SELECT SUM({METRIC_COL}) FROM {TABLE} WHERE D_DATE_KEY = '{MONTH}';
```

## Feature Testing Templates

### Business Rule Validation
```sql
-- Positive test: All records matching condition should have expected result
-- Example: Deleted wallets should be ineligible
SELECT COUNT(*) AS violations
FROM {TABLE}
WHERE {CONDITION_TRUE}
  AND NOT {EXPECTED_RESULT}
  AND CURRENT_RECORD_IND = 1;
-- Expected: 0 violations
```

### State Transition Check
```sql
-- Verify state changes follow expected pattern
-- Example: Check PP_2_OA transitions
SELECT
    prev.wallet_type AS from_type,
    curr.wallet_type AS to_type,
    curr.action,
    COUNT(*) AS cnt
FROM {TABLE} curr
JOIN {TABLE} prev
  ON curr.wallet_member_key = prev.wallet_member_key
  AND curr.version_no = prev.version_no + 1
WHERE curr.action = '{TRANSITION_ACTION}'
  AND curr.CURRENT_RECORD_IND = 1
GROUP BY 1, 2, 3;
```

### Priority/Suppression Logic
```sql
-- Example: OA should suppress PP for same MSISDN
-- Find cases where both OA and PP are active for same wallet_id
SELECT wallet_id, COUNT(DISTINCT wallet_type) AS type_count
FROM {TABLE}
WHERE CURRENT_RECORD_IND = 1
  AND wallet_eligibility_flag = 'Y'
GROUP BY wallet_id
HAVING COUNT(DISTINCT wallet_type) > 1;
-- Expected: 0 rows (no dual-active)
```

### Edge Case: Same-Day Multiple Actions
```sql
-- Check for multiple current records (SCD2 overlap risk)
SELECT wallet_member_key, COUNT(*) AS current_count
FROM {TABLE}
WHERE CURRENT_RECORD_IND = 1
GROUP BY wallet_member_key
HAVING COUNT(*) > 1;
-- Expected: 0 rows
```

### Calculation Validation
```sql
-- Verify calculated field matches expected formula
SELECT *
FROM {TABLE}
WHERE ABS({CALCULATED_COL} - ({FORMULA})) > 0.01
  AND CURRENT_RECORD_IND = 1
LIMIT 100;
```

## Regression Testing Templates

### Baseline Capture
```sql
-- Run BEFORE the change, save results
SELECT
    '{BASELINE_ID}' AS baseline_id,
    '{TABLE}' AS table_name,
    {DIMENSION_COL} AS dimension,
    COUNT(*) AS row_count,
    SUM({METRIC_COL}) AS metric_sum
FROM {TABLE}
WHERE CURRENT_RECORD_IND = 1
GROUP BY {DIMENSION_COL};
```

### Before/After Comparison
```sql
-- Compare current state to baseline
WITH baseline AS (
    -- Paste baseline results or use a saved table
    SELECT 'OA' AS dimension, 1000000 AS row_count, 5000000.00 AS metric_sum
    UNION ALL SELECT 'PP', 500000, 2000000.00
    UNION ALL SELECT 'NC', 200000, 100000.00
),
current_state AS (
    SELECT
        {DIMENSION_COL} AS dimension,
        COUNT(*) AS row_count,
        SUM({METRIC_COL}) AS metric_sum
    FROM {TABLE}
    WHERE CURRENT_RECORD_IND = 1
    GROUP BY {DIMENSION_COL}
)
SELECT
    COALESCE(b.dimension, c.dimension) AS dimension,
    b.row_count AS baseline_count,
    c.row_count AS current_count,
    c.row_count - b.row_count AS count_diff,
    ROUND(100.0 * (c.row_count - b.row_count) / NULLIF(b.row_count, 0), 2) AS count_pct_change,
    b.metric_sum AS baseline_sum,
    c.metric_sum AS current_sum,
    c.metric_sum - b.metric_sum AS sum_diff
FROM baseline b
FULL OUTER JOIN current_state c ON b.dimension = c.dimension
ORDER BY ABS(count_pct_change) DESC NULLS LAST;
```

### Distribution Shift Detection
```sql
-- Detect if distribution changed significantly
SELECT
    {CATEGORY_COL},
    COUNT(*) AS cnt,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct
FROM {TABLE}
WHERE CURRENT_RECORD_IND = 1
GROUP BY {CATEGORY_COL}
ORDER BY cnt DESC;
-- Compare percentages to baseline; flag if shift > 2%
```

### NULL Introduction Check
```sql
-- Check if NULLs appeared in previously non-null columns
SELECT
    '{COL1}' AS column_name,
    COUNT(*) AS total,
    COUNT({COL1}) AS non_null,
    COUNT(*) - COUNT({COL1}) AS null_count,
    ROUND(100.0 * (COUNT(*) - COUNT({COL1})) / COUNT(*), 2) AS null_pct
FROM {TABLE}
WHERE CURRENT_RECORD_IND = 1

UNION ALL

SELECT '{COL2}', COUNT(*), COUNT({COL2}), COUNT(*) - COUNT({COL2}),
       ROUND(100.0 * (COUNT(*) - COUNT({COL2})) / COUNT(*), 2)
FROM {TABLE}
WHERE CURRENT_RECORD_IND = 1;
```

### Snapshot Continuity Check
```sql
-- Verify no gaps in daily snapshots
SELECT
    snapshot_date,
    LAG(snapshot_date) OVER (ORDER BY snapshot_date) AS prev_date,
    DATEDIFF('day', LAG(snapshot_date) OVER (ORDER BY snapshot_date), snapshot_date) AS gap_days
FROM (SELECT DISTINCT snapshot_date FROM {TABLE})
HAVING gap_days > 1
ORDER BY snapshot_date;
-- Expected: 0 rows (no gaps)
```

## Migration QA - Insert Templates

Output only the AZURE insert template. Add: "Run the same SQL in AWS by changing SOURCE_ENV to 'AWS_PROD'."

### Core Checks Template
```sql
-- Template: Replace {TABLE}, {RUN_ID}, {FILTER}, {METRIC_COL}
INSERT INTO prod_wallet.work.zz_qa_migration_test_results
(RUN_ID, SOURCE_ENV, TABLE_NAME, TEST_CATEGORY, TEST_NAME, DIMENSION_NAME, METRIC_VALUE, STATUS, DETAILS, NOTES)

-- Row count
SELECT '{RUN_ID}', 'AZURE_PROD', '{TABLE}', 'COUNT', 'row_count',
       NULL, TO_VARCHAR(COUNT(*)), 'RECORDED', NULL, NULL
FROM {TABLE} WHERE {FILTER}

UNION ALL
-- Date boundary
SELECT '{RUN_ID}', 'AZURE_PROD', '{TABLE}', 'DATE_RANGE', 'min_max_date',
       '{DATE_COL}', MIN({DATE_COL}) || '|' || MAX({DATE_COL}), 'RECORDED', NULL, NULL
FROM {TABLE} WHERE {FILTER}

UNION ALL
-- Key metric SUM
SELECT '{RUN_ID}', 'AZURE_PROD', '{TABLE}', 'FINANCIAL', 'sum',
       '{METRIC_COL}', TO_VARCHAR(SUM({METRIC_COL})), 'RECORDED', NULL, NULL
FROM {TABLE} WHERE {FILTER};
```

### Category Distribution Template
```sql
INSERT INTO prod_wallet.work.zz_qa_migration_test_results
SELECT '{RUN_ID}', 'AZURE_PROD', '{TABLE}', 'DISTRIBUTION', 'category_count',
       {DIM_COL}, TO_VARCHAR(COUNT(*)), 'RECORDED', NULL, NULL
FROM {TABLE} WHERE {FILTER}
GROUP BY {DIM_COL};
```

### SCD2 Version Check Template
```sql
INSERT INTO prod_wallet.work.zz_qa_migration_test_results
SELECT '{RUN_ID}', 'AZURE_PROD', '{TABLE}', 'SCD2', 'version_distribution',
       TO_VARCHAR(CURRENT_RECORD_IND), TO_VARCHAR(COUNT(*)), 'RECORDED', NULL, NULL
FROM {TABLE}
GROUP BY CURRENT_RECORD_IND;
```

### Timing Alignment Template
```sql
-- Check timing alignment (critical for dbt re-run migration)
INSERT INTO prod_wallet.work.zz_qa_migration_test_results
SELECT '{RUN_ID}', 'AZURE_PROD', '{TABLE}', 'TIMING', 'record_timestamp_range',
       'RECORD_START_DATE_TIME',
       MIN(RECORD_START_DATE_TIME) || '|' || MAX(RECORD_START_DATE_TIME),
       'RECORDED', NULL, 'Compare with AWS to detect source data drift'
FROM {TABLE}
WHERE CURRENT_RECORD_IND = 1;
```

## Root Cause Analysis (on FAIL)

When metrics don't match, investigate in this order:

### 1. Timing Alignment (Check First)
dbt re-run approach means source data may differ between Azure/AWS runs.

```sql
-- Compare record timestamps between environments
SELECT
    MIN(RECORD_START_DATE_TIME) AS earliest,
    MAX(RECORD_START_DATE_TIME) AS latest,
    COUNT(*) AS total_rows
FROM {TABLE}
WHERE CURRENT_RECORD_IND = 1;
```

If `latest` timestamps differ → source data changed between runs (expected drift).

### 2. Other Investigation Paths

| # | Check | What to Look For |
|---|-------|------------------|
| 2 | Filter alignment | CURRENT_RECORD_IND, eligibility, date filters differ |
| 3 | Key population | Count distinct grain keys to isolate new/missing records |
| 4 | Dimension split | Break down by wallet_type to isolate drift source |
| 5 | Value distribution | Use percentiles to see if drift is in outliers or spread evenly |

```sql
-- Percentile check when SUM mismatch
SELECT
    COUNT(*) AS cnt,
    SUM({COL}) AS total,
    MEDIAN({COL}) AS p50,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY {COL}) AS p95
FROM {TABLE} WHERE {FILTER};
```

## Constraints

- SELECT only (read-only) unless INSERT to QA results table
- Always use LIMIT for exploratory queries
- Use exact column names from schema (case-sensitive)

---

## Common Wallet QA Templates

### Wallet Population Summary
```sql
-- Quick overview of wallet ecosystem
SELECT
    wallet_type,
    wallet_eligibility_flag,
    COUNT(*) AS wallet_count,
    COUNT(DISTINCT wallet_id) AS unique_msisdn
FROM ds_yt_wallet_management
WHERE CURRENT_RECORD_IND = 1
GROUP BY 1, 2
ORDER BY 1, 2;
```

### Balance Reconciliation Check
```sql
-- Verify balance integrity: earned = available + redeemed + expired + void
SELECT
    wallet_member_key,
    balance_earned,
    balance_available + balance_redeemed + balance_expired + balance_void AS calculated_total,
    balance_earned - (balance_available + balance_redeemed + balance_expired + balance_void) AS diff
FROM ds_yt_daily_snapshot
WHERE snapshot_date = '{DATE}'
  AND ABS(balance_earned - (balance_available + balance_redeemed + balance_expired + balance_void)) > 0.01
LIMIT 100;
```

### Lifecycle Action Distribution
```sql
-- Understand recent wallet activity by action type
SELECT
    action,
    wallet_type,
    COUNT(*) AS cnt,
    MIN(record_start_date_time) AS earliest,
    MAX(record_start_date_time) AS latest
FROM ds_yt_wallet_management
WHERE record_start_date_time >= DATEADD('day', -7, CURRENT_DATE())
GROUP BY 1, 2
ORDER BY cnt DESC;
```

### Dosh Customer Status
```sql
-- Check Dosh customer flags and delete dates
SELECT
    dosh_customer_flag,
    CASE WHEN wallet_delete_date IS NULL THEN 'NO_DELETE' ELSE 'HAS_DELETE' END AS delete_status,
    COUNT(*) AS cnt
FROM ds_yt_wallet_management
WHERE CURRENT_RECORD_IND = 1
  AND (dosh_customer_flag = 'Y' OR wallet_type = 'NON-CUSTOMER')
GROUP BY 1, 2;
```

### Event Deduplication Check
```sql
-- Find duplicate events (should be 0 within 5-day window)
SELECT
    business_event_key,
    COUNT(*) AS occurrences
FROM ds_yt_business_events
WHERE event_timestamp >= DATEADD('day', -5, CURRENT_DATE())
GROUP BY business_event_key
HAVING COUNT(*) > 1;
```

### Daily Snapshot Completeness
```sql
-- Verify no missing snapshot dates in date range
WITH date_spine AS (
    SELECT DATEADD('day', seq4(), '{START_DATE}') AS expected_date
    FROM TABLE(GENERATOR(ROWCOUNT => DATEDIFF('day', '{START_DATE}', '{END_DATE}') + 1))
),
actual_dates AS (
    SELECT DISTINCT snapshot_date FROM ds_yt_daily_snapshot
    WHERE snapshot_date BETWEEN '{START_DATE}' AND '{END_DATE}'
)
SELECT d.expected_date AS missing_date
FROM date_spine d
LEFT JOIN actual_dates a ON d.expected_date = a.snapshot_date
WHERE a.snapshot_date IS NULL
ORDER BY missing_date;
```

### Score Distribution Analysis
```sql
-- Analyze ML score distributions
SELECT
    CASE
        WHEN churn_score < 0.2 THEN '0-20%'
        WHEN churn_score < 0.5 THEN '20-50%'
        WHEN churn_score < 0.8 THEN '50-80%'
        ELSE '80-100%'
    END AS churn_band,
    COUNT(*) AS wallet_count,
    ROUND(AVG(clv_score), 2) AS avg_clv
FROM ds_yt_wallet_scores
WHERE CURRENT_RECORD_IND = 1
GROUP BY 1
ORDER BY 1;
```

---

## Quick Diagnosis Templates

### Find Sample Records
```sql
-- Get sample records for a specific condition
SELECT *
FROM {TABLE}
WHERE {CONDITION}
  AND CURRENT_RECORD_IND = 1
LIMIT 10;
```

### Trace Wallet History
```sql
-- Full SCD2 history for a specific wallet
SELECT
    version_no,
    action,
    wallet_type,
    wallet_eligibility_flag,
    service_status_name,
    record_start_date_time,
    record_end_date_time,
    current_record_ind
FROM ds_yt_wallet_management
WHERE wallet_member_key = '{WMK}'
ORDER BY version_no;
```

### Compare Two Snapshots
```sql
-- Quick delta between two snapshot dates
SELECT
    '{DATE1}' AS snapshot,
    COUNT(*) AS total_wallets,
    SUM(balance_available) AS total_available,
    SUM(balance_redeemed) AS total_redeemed
FROM ds_yt_daily_snapshot WHERE snapshot_date = '{DATE1}'
UNION ALL
SELECT
    '{DATE2}',
    COUNT(*),
    SUM(balance_available),
    SUM(balance_redeemed)
FROM ds_yt_daily_snapshot WHERE snapshot_date = '{DATE2}';
```

### Identify Outliers
```sql
-- Find outlier balances (> 3 std dev from mean)
WITH stats AS (
    SELECT AVG(balance_available) AS avg_bal, STDDEV(balance_available) AS std_bal
    FROM ds_yt_daily_snapshot WHERE snapshot_date = '{DATE}'
)
SELECT d.*
FROM ds_yt_daily_snapshot d, stats s
WHERE d.snapshot_date = '{DATE}'
  AND ABS(d.balance_available - s.avg_bal) > 3 * s.std_bal
LIMIT 100;
```

---

## Data Quality Report Template

### Full Table Health Check
```sql
-- Comprehensive single-table health report
SELECT
    '{TABLE}' AS table_name,
    'row_count' AS metric,
    TO_VARCHAR(COUNT(*)) AS value
FROM {TABLE} WHERE CURRENT_RECORD_IND = 1

UNION ALL SELECT '{TABLE}', 'distinct_grain', TO_VARCHAR(COUNT(DISTINCT {GRAIN_COL}))
FROM {TABLE} WHERE CURRENT_RECORD_IND = 1

UNION ALL SELECT '{TABLE}', 'duplicate_grains',
    TO_VARCHAR((SELECT COUNT(*) FROM (
        SELECT {GRAIN_COL} FROM {TABLE} WHERE CURRENT_RECORD_IND = 1
        GROUP BY {GRAIN_COL} HAVING COUNT(*) > 1
    )))

UNION ALL SELECT '{TABLE}', 'null_pct_{COL1}',
    TO_VARCHAR(ROUND(100.0 * SUM(CASE WHEN {COL1} IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2))
FROM {TABLE} WHERE CURRENT_RECORD_IND = 1

UNION ALL SELECT '{TABLE}', 'date_range',
    MIN({DATE_COL}) || ' to ' || MAX({DATE_COL})
FROM {TABLE} WHERE CURRENT_RECORD_IND = 1;
