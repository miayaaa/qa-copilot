# Wallet Migration QA Context

> **For Migration QA Mode Only**
> Load this context when comparing Azure vs AWS environments.

## Platform Migration: Azure to AWS

The Wallet data platform is migrating from Azure to AWS cloud environment.

## Migration Approach: dbt Re-run (NOT Data Copy)

| Aspect | Detail |
|--------|--------|
| Method | Re-run dbt pipeline in AWS, **not** direct data copy |
| First Run | Full load (`is_incremental() = false`) |
| Data Source | Same Snowflake source system (e.g., `pdb_modelled`) |
| Storage Change | Azure ADLS to AWS S3 (external stages only) |
| Schema/Tables | Names unchanged between environments |

### Benefits

- **Data consistency**: Regenerated from source, avoids copy errors
- **Code consistency**: Same dbt code runs in both Azure and AWS
- **Incremental ready**: After first full load, subsequent runs process only incremental data

## QA Implications

### Expected to Match

- Row counts (same source, same dbt logic)
- Key metrics (balance_redeemed, CLV, churn scores)
- Grain uniqueness
- Category distributions

### Potential Drift Sources

| Cause | Impact | Detection |
|-------|--------|-----------|
| Run timing difference | Source data changed between Azure/AWS dbt runs | Compare `MAX(RECORD_START_DATE_TIME)` |
| Incremental vs full | Azure has incremental history, AWS is fresh full load | Compare `MIN(RECORD_START_DATE_TIME)` |
| Late-arriving source records | Records added to source after Azure run | Compare distinct grain key counts |
| Timezone/cutoff drift | Different run schedules | Compare date boundaries |
| **AWS manual updates** | Data engineers sometimes apply manual fixes in AWS | `RECORD_START_DATE_TIME` may not match exactly |

## First Check on Mismatch: Timing Alignment

When metrics don't match, **always check timing first**:

```sql
-- Compare latest record timestamps (run in each environment)
SELECT 'AZURE' AS env, MAX(RECORD_START_DATE_TIME) AS latest_record
FROM {TABLE}
WHERE CURRENT_RECORD_IND = 1;

-- In AWS, run same query with 'AWS' label
```

If timestamps differ significantly, the source data changed between runs - this explains most "drift."

## Known AWS Limitations (NON-CUSTOMER)

| Gap Type | Cause |
|----------|-------|
| PDB→MATRIXX timing | Multi-day batch load missed transient records |
| Microsite late arrivals | NON-CUSTOMER created near cutoff (before 18:00) not yet in AWS |

> AWS NON-CUSTOMER count may be lower than Azure due to load timing windows.

## Migration QA Priority Metrics

| Priority | Metric | Table | Column(s) | Why Important |
|----------|--------|-------|-----------|---------------|
| P1 | Row Count | All | - | Data completeness |
| P1 | Balance Redeemed | ds_yt_daily_snapshot | balance_redeemed | Financial reconciliation |
| P1 | CLV Amount | ds_yt_wallet_scores | MOB_OA_CONSUM_CLV_AMOUNT | Business value metric |
| P2 | Wallet Eligibility | ds_yt_wallet_customer | wallet_eligibility_flag | Active customer count |
| P2 | Churn Score | ds_yt_wallet_scores | MOB_OA_CONSUM_CHURN_SCORE | ML model accuracy |
| P3 | Category Distribution | All | wallet_type, service_status | Data quality |

## Results Table

```
prod_wallet.work.zz_qa_migration_test_results
```

| Column | Purpose |
|--------|---------|
| RUN_ID | Unique identifier for test run |
| SOURCE_ENV | AZURE_PROD or AWS_PROD |
| TABLE_NAME | Table being tested |
| TEST_CATEGORY | COUNT, DISTRIBUTION, FINANCIAL, SCD2, TIMING |
| TEST_NAME | Specific test name |
| DIMENSION_NAME | Dimension column if applicable |
| METRIC_VALUE | Test result value |
| STATUS | RECORDED, PASS, FAIL |
| DETAILS | Additional details |
| NOTES | Notes for investigation |
