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
work.zz_qa_migration_comparison_results
-- Columns: RUN_ID, RUN_DATE, TABLE_NAME, TEST_CATEGORY, TEST_NAME,
--          DIMENSION_NAME, AZURE_VALUE, AWS_VALUE, VARIANCE_VALUE,
--          VARIANCE_PCT, MATCH_STATUS, NOTES
```

### Core Checks (INSERT)
```sql
INSERT INTO work.zz_qa_migration_comparison_results
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
INSERT INTO work.zz_qa_migration_comparison_results
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

## Constraints

- SELECT only (read-only) unless INSERT to QA results table
- Always use LIMIT for exploratory queries
- Use exact column names from schema (case-sensitive)