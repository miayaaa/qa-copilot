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

-- Grain uniqueness on current records
SELECT {GRAIN_COLS}, COUNT(*) AS cnt
FROM {TABLE}
WHERE CURRENT_RECORD_IND = 1
GROUP BY {GRAIN_COLS}
HAVING COUNT(*) > 1;

-- SCD2 version distribution
SELECT CURRENT_RECORD_IND, COUNT(*) AS cnt
FROM {TABLE}
GROUP BY CURRENT_RECORD_IND;
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

-- Time boundary check
SELECT MIN(EVENT_TIMESTAMP), MAX(EVENT_TIMESTAMP) FROM {TABLE};

-- Event type distribution
SELECT EVENT_TYPE, COUNT(*) AS cnt
FROM {TABLE}
GROUP BY EVENT_TYPE
ORDER BY cnt DESC;
```

### Monthly Fact Tables
```sql
-- Row count for month
SELECT COUNT(*) FROM {TABLE} WHERE D_DATE_KEY = '{MONTH}';

-- Key metrics SUM for month
SELECT SUM({METRIC_COL}) FROM {TABLE} WHERE D_DATE_KEY = '{MONTH}';
```

---

## Migration QA Templates

### Results Table
```sql
work.zzmy_qa_migration_comparison_results
-- Columns: RUN_ID, RUN_DATE, TABLE_NAME, TEST_CATEGORY, TEST_NAME,
--          DIMENSION_NAME, AZURE_VALUE, AWS_VALUE, VARIANCE_VALUE,
--          VARIANCE_PCT, MATCH_STATUS, NOTES
```

### Core Checks (INSERT)
```sql
INSERT INTO work.zzmy_qa_migration_comparison_results
(RUN_ID, TABLE_NAME, TEST_CATEGORY, TEST_NAME, DIMENSION_NAME, AZURE_VALUE, AWS_VALUE, VARIANCE_VALUE, VARIANCE_PCT, MATCH_STATUS, NOTES)

WITH azure AS (
    SELECT COUNT(*) AS cnt FROM {AZURE_TABLE} WHERE {FILTER}
),
aws AS (
    SELECT COUNT(*) AS cnt FROM {AWS_TABLE} WHERE {FILTER}
)
SELECT
    '{RUN_ID}', '{TABLE}', 'COUNT', 'row_count', NULL,
    TO_VARCHAR(azure.cnt), TO_VARCHAR(aws.cnt),
    TO_VARCHAR(aws.cnt - azure.cnt),
    TO_VARCHAR(ROUND(100.0 * (aws.cnt - azure.cnt) / NULLIF(azure.cnt, 0), 2)) || '%',
    CASE WHEN azure.cnt = aws.cnt THEN 'MATCH' ELSE 'MISMATCH' END,
    NULL
FROM azure, aws;
```

### Category Distribution (INSERT)
```sql
INSERT INTO work.zzmy_qa_migration_comparison_results
WITH azure AS (
    SELECT {DIM_COL} AS dim, COUNT(*) AS cnt FROM {AZURE_TABLE} WHERE {FILTER} GROUP BY {DIM_COL}
),
aws AS (
    SELECT {DIM_COL} AS dim, COUNT(*) AS cnt FROM {AWS_TABLE} WHERE {FILTER} GROUP BY {DIM_COL}
)
SELECT
    '{RUN_ID}', '{TABLE}', 'DISTRIBUTION', 'category_count',
    COALESCE(azure.dim, aws.dim),
    TO_VARCHAR(azure.cnt), TO_VARCHAR(aws.cnt),
    TO_VARCHAR(COALESCE(aws.cnt, 0) - COALESCE(azure.cnt, 0)),
    TO_VARCHAR(ROUND(100.0 * (COALESCE(aws.cnt, 0) - COALESCE(azure.cnt, 0)) / NULLIF(azure.cnt, 0), 2)) || '%',
    CASE WHEN azure.cnt = aws.cnt THEN 'MATCH' ELSE 'MISMATCH' END,
    NULL
FROM azure FULL OUTER JOIN aws ON azure.dim = aws.dim;
```

### Cross-Environment Comparison (Staging Table Join)

When Azure data is loaded into a staging table, compare directly via JOIN.

```sql
-- Records in Azure but NOT in AWS
SELECT az.*
FROM   work.{staging_table}  az
WHERE NOT EXISTS (
    SELECT NULL
    FROM   modelled.{aws_table}  aws
    WHERE  aws.current_record_ind = 1
    AND    aws.{join_key} = az.{join_key}
);

-- Records in AWS but NOT in Azure
SELECT aws.*
FROM   modelled.{aws_table}  aws
WHERE  aws.current_record_ind = 1
AND NOT EXISTS (
    SELECT NULL
    FROM   work.{staging_table}  az
    WHERE  az.{join_key} = aws.{join_key}
);
```

---

## Root Cause Analysis (on FAIL)

### 1. Timing Alignment (Check First)
```sql
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

---

## Regression Testing Templates

### Baseline Table
```sql
-- work.zzmy_qa_regression_baseline
-- Columns: baseline_id, baseline_date, table_name, check_type,
--          dimension_name, dimension_value, metric_value, filter_applied
```

### Save Baseline (One Table)
```sql
-- Save baseline for {TABLE}
INSERT INTO work.zzmy_qa_regression_baseline
(baseline_id, baseline_date, table_name, check_type, dimension_name, dimension_value, metric_value, filter_applied, created_by, created_at)
-- Row count
SELECT MD5('{TABLE}' || CURRENT_TIMESTAMP()), CURRENT_TIMESTAMP(),
       '{SCHEMA}.{TABLE}', 'row_count', NULL, NULL, COUNT(*),
       '{FILTER}', CURRENT_USER(), CURRENT_TIMESTAMP()
FROM {SCHEMA}.{TABLE} WHERE {FILTER}
UNION ALL
-- Category distribution
SELECT MD5('{TABLE}' || CURRENT_TIMESTAMP()), CURRENT_TIMESTAMP(),
       '{SCHEMA}.{TABLE}', 'category_dist', '{DIM_COL}', {DIM_COL}::VARCHAR, COUNT(*),
       '{FILTER}', CURRENT_USER(), CURRENT_TIMESTAMP()
FROM {SCHEMA}.{TABLE} WHERE {FILTER}
GROUP BY {DIM_COL};
```

### Compare to Baseline
```sql
-- Compare current vs baseline for {TABLE}
WITH baseline AS (
    SELECT * FROM work.zzmy_qa_regression_baseline
    WHERE baseline_id = '{BASELINE_ID}'
),
current_row_count AS (
    SELECT 'row_count' AS check_type, NULL AS dimension_name, NULL AS dimension_value, COUNT(*) AS metric_value
    FROM {SCHEMA}.{TABLE} WHERE {FILTER}
),
current_dist AS (
    SELECT 'category_dist' AS check_type, '{DIM_COL}' AS dimension_name, {DIM_COL}::VARCHAR AS dimension_value, COUNT(*) AS metric_value
    FROM {SCHEMA}.{TABLE} WHERE {FILTER}
    GROUP BY {DIM_COL}
),
current_metrics AS (
    SELECT * FROM current_row_count UNION ALL SELECT * FROM current_dist
)
SELECT
    b.table_name,
    c.check_type,
    c.dimension_name,
    c.dimension_value,
    b.metric_value AS baseline_value,
    c.metric_value AS current_value,
    (c.metric_value - b.metric_value) AS variance,
    ROUND(100.0 * (c.metric_value - b.metric_value) / NULLIF(b.metric_value, 0), 2) AS variance_pct,
    CASE
        WHEN ABS(c.metric_value - b.metric_value) / NULLIF(b.metric_value, 0) > 0.01 THEN 'FAIL'
        WHEN ABS(c.metric_value - b.metric_value) / NULLIF(b.metric_value, 0) > 0.001 THEN 'WARN'
        ELSE 'PASS'
    END AS status
FROM baseline b
FULL OUTER JOIN current_metrics c
  ON b.check_type = c.check_type
  AND IFNULL(b.dimension_name,'') = IFNULL(c.dimension_name,'')
  AND IFNULL(b.dimension_value,'') = IFNULL(c.dimension_value,'')
ORDER BY status DESC, check_type, dimension_value;
```

### SCD2 History Immutability
```sql
-- Check historical records unchanged (current_record_ind = 0)
-- Requires baseline snapshot table: {TABLE}_baseline
WITH baseline_hash AS (
    SELECT {GRAIN}, version_no,
           MD5(CONCAT_WS('|', {COMPARE_COLS})) AS row_hash
    FROM {TABLE}_baseline WHERE current_record_ind = 0
),
current_hash AS (
    SELECT {GRAIN}, version_no,
           MD5(CONCAT_WS('|', {COMPARE_COLS})) AS row_hash
    FROM {TABLE} WHERE current_record_ind = 0
)
SELECT
    'history_immutable' AS check_type,
    COUNT(CASE WHEN b.row_hash IS NULL THEN 1 END) AS new_records,
    COUNT(CASE WHEN c.row_hash IS NULL THEN 1 END) AS deleted_records,
    COUNT(CASE WHEN b.row_hash IS NOT NULL AND c.row_hash IS NOT NULL AND b.row_hash != c.row_hash THEN 1 END) AS modified_records,
    CASE WHEN COUNT(CASE WHEN b.row_hash IS NULL OR c.row_hash IS NULL OR b.row_hash != c.row_hash THEN 1 END) = 0
         THEN 'PASS' ELSE 'FAIL' END AS status
FROM baseline_hash b
FULL OUTER JOIN current_hash c
  ON b.{GRAIN} = c.{GRAIN} AND b.version_no = c.version_no;
```

### Quick Baseline Commands

| Table Type | Default Checks | Default Filter |
|------------|----------------|----------------|
| SCD2 | row_count, category_dist(wallet_type, action) | `current_record_ind = 1` |
| Snapshot | row_count, aggregate_sum(balance*) | `d_date_key = today` |
| Incremental | row_count by date | `d_date_key >= cutoff` |

---

## Constraints

- SELECT only (read-only) unless INSERT to QA results table
- Always use LIMIT for exploratory queries
- Use exact column names from schema (case-sensitive)