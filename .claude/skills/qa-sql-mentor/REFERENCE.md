# Snowflake SQL Quick Reference

## Syntax Essentials

```sql
-- Timestamps
DATE(ts_col)                              -- Extract date
DATEADD(day, -7, CURRENT_TIMESTAMP())     -- Date math
DATEDIFF(day, start_col, end_col)         -- Date diff
DATE_TRUNC('hour', ts_col)                -- Truncate

-- NULLs
COALESCE(col, 'default')                  -- First non-null
NVL(col, 'default')                       -- Same, 2 args
NULLIF(col, '')                           -- Value to NULL
col IS NOT DISTINCT FROM val              -- NULL-safe equals

-- Strings
col ILIKE '%pattern%'                     -- Case-insensitive
REGEXP_LIKE(col, '^[A-Z]{2}$')            -- Regex match

-- Window + QUALIFY (Snowflake-specific)
COUNT(*) OVER (PARTITION BY col)          -- Window count
QUALIFY row_num = 1                       -- Filter window results
```

## QA Pattern Shortcuts

| Check | Pattern |
|-------|---------|
| Duplicates | `GROUP BY key HAVING COUNT(*) > 1` |
| Orphans | `LEFT JOIN parent ON fk WHERE parent.pk IS NULL` |
| NULL % | `100.0 * (COUNT(*) - COUNT(col)) / COUNT(*)` |
| Enum violations | `WHERE status NOT IN ('A','B','C')` |
| Time order | `WHERE end_ts < start_ts` |
| Balance mismatch | `WHERE ABS(recorded - calculated) > 0.01` |

## Migration QA - 3 Step Approach

### Step 1: Run in AZURE (INSERT to AWS results table)

```sql
-- Template: Replace {TABLE}, {RUN_ID}, {DATE_COL}, {AMOUNT_COL}
INSERT INTO prod_wallet.work.zz_qa_migration_test_results
(RUN_ID, SOURCE_ENV, TABLE_NAME, TEST_CATEGORY, TEST_NAME, DIMENSION_NAME, METRIC_VALUE, STATUS, DETAILS, NOTES)

-- Row count
SELECT '{RUN_ID}', 'AZURE_PROD', '{TABLE}', 'COUNT', 'row_count',
       NULL, TO_VARCHAR(COUNT(*)), 'RECORDED', NULL, NULL
FROM {TABLE} WHERE CURRENT_RECORD_IND = 1

UNION ALL
-- Date range
SELECT '{RUN_ID}', 'AZURE_PROD', '{TABLE}', 'DATE_RANGE', 'min_max_date',
       '{DATE_COL}', MIN({DATE_COL}) || '|' || MAX({DATE_COL}), 'RECORDED', NULL, NULL
FROM {TABLE} WHERE CURRENT_RECORD_IND = 1

UNION ALL
-- Financial SUM
SELECT '{RUN_ID}', 'AZURE_PROD', '{TABLE}', 'FINANCIAL', 'sum',
       '{AMOUNT_COL}', TO_VARCHAR(SUM({AMOUNT_COL})), 'RECORDED', NULL, NULL
FROM {TABLE} WHERE CURRENT_RECORD_IND = 1;
```

### Step 2: Run in AWS (same SQL, change SOURCE_ENV)

```sql
-- Same structure, change AZURE_PROD → AWS_PROD
INSERT INTO prod_wallet.work.zz_qa_migration_test_results
(RUN_ID, SOURCE_ENV, TABLE_NAME, TEST_CATEGORY, TEST_NAME, DIMENSION_NAME, METRIC_VALUE, STATUS, DETAILS, NOTES)

SELECT '{RUN_ID}', 'AWS_PROD', '{TABLE}', 'COUNT', 'row_count',
       NULL, TO_VARCHAR(COUNT(*)), 'RECORDED', NULL, NULL
FROM {TABLE} WHERE CURRENT_RECORD_IND = 1

UNION ALL
SELECT '{RUN_ID}', 'AWS_PROD', '{TABLE}', 'DATE_RANGE', 'min_max_date',
       '{DATE_COL}', MIN({DATE_COL}) || '|' || MAX({DATE_COL}), 'RECORDED', NULL, NULL
FROM {TABLE} WHERE CURRENT_RECORD_IND = 1

UNION ALL
SELECT '{RUN_ID}', 'AWS_PROD', '{TABLE}', 'FINANCIAL', 'sum',
       '{AMOUNT_COL}', TO_VARCHAR(SUM({AMOUNT_COL})), 'RECORDED', NULL, NULL
FROM {TABLE} WHERE CURRENT_RECORD_IND = 1;
```

### Step 3: Compare (Run in AWS)

```sql
-- Auto-compare results and UPDATE status
UPDATE prod_wallet.work.zz_qa_migration_test_results tgt
SET STATUS = CASE WHEN tgt.METRIC_VALUE = src.METRIC_VALUE THEN 'PASS' ELSE 'FAIL' END,
    DETAILS = 'AZURE: ' || src.METRIC_VALUE || ' | AWS: ' || tgt.METRIC_VALUE
FROM prod_wallet.work.zz_qa_migration_test_results src
WHERE tgt.RUN_ID = '{RUN_ID}'
  AND src.RUN_ID = '{RUN_ID}'
  AND tgt.SOURCE_ENV = 'AWS_PROD'
  AND src.SOURCE_ENV = 'AZURE_PROD'
  AND tgt.TABLE_NAME = src.TABLE_NAME
  AND tgt.TEST_NAME = src.TEST_NAME
  AND NVL(tgt.DIMENSION_NAME, '') = NVL(src.DIMENSION_NAME, '');

-- View results
SELECT * FROM prod_wallet.work.zz_qa_migration_test_results
WHERE RUN_ID = '{RUN_ID}' AND SOURCE_ENV = 'AWS_PROD'
ORDER BY STATUS DESC, TEST_CATEGORY;
```

## Category Distribution (Optional)

```sql
-- Run in each env, adds one row per category value
INSERT INTO prod_wallet.work.zz_qa_migration_test_results
SELECT '{RUN_ID}', '{ENV}', '{TABLE}', 'DISTRIBUTION', 'category_count',
       {DIM_COL}, TO_VARCHAR(COUNT(*)), 'RECORDED', NULL, NULL
FROM {TABLE} WHERE CURRENT_RECORD_IND = 1
GROUP BY {DIM_COL};
```

## Root Cause Analysis (Level 2)

```sql
-- Percentiles when SUM mismatch
SELECT
    MEDIAN({AMOUNT_COL}) AS p50,
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY {AMOUNT_COL}) AS p25,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY {AMOUNT_COL}) AS p75,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY {AMOUNT_COL}) AS p95
FROM {TABLE} WHERE CURRENT_RECORD_IND = 1;
```

## Constraints

- SELECT only (read-only) unless INSERT to QA results requested
- Always use LIMIT for exploration
- Prefer QUALIFY over subqueries
