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

## Constraints

- SELECT only (read-only)
- Always use LIMIT for exploration
- Prefer QUALIFY over subqueries
