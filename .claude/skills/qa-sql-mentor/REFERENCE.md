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

## Root Cause Analysis (on FAIL)

When metrics don't match, suggest these investigation paths:

1. **Filter alignment** - Check if CURRENT_RECORD_IND, eligibility, or date filters differ
2. **Time boundary** - Compare min/max timestamps for timezone or cutoff drift
3. **Key population** - Count distinct grain keys to isolate new/missing records
4. **Dimension split** - Break down by wallet_type or other category to isolate drift source
5. **Value distribution** - Use percentiles to see if drift is in outliers or spread evenly

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
