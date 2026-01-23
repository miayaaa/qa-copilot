# Wallet Regression Test Framework

> Automated regression testing via dbt macro.

## Quick Start

```bash
# First time: create tables
dbt run-operation regression_init

# Before code change: save baseline
dbt run-operation regression_baseline --args '{"table_name": "ds_yt_wallet_customer"}'

# After code change: compare
dbt run-operation regression_compare --args '{"table_name": "ds_yt_wallet_customer"}'
```

## Available Macros

| Macro | Purpose |
|-------|---------|
| `regression_init()` | Create baseline/results tables (run once) |
| `regression_baseline(table)` | Save current metrics as baseline |
| `regression_compare(table)` | Compare current vs baseline |
| `regression_test(table)` | Auto: compare if baseline exists, else save |

## Supported Tables

| Table | Type | Auto Filter | Auto Dimensions |
|-------|------|-------------|-----------------|
| ds_yt_wallet_customer | SCD2 | `current_record_ind = 1` | wallet_type, wallet_eligibility_flag |
| ds_yt_wallet_management | SCD2 | `current_record_ind = 1` | wallet_type, action |
| ds_yt_wallet_daily_ss | Snapshot | `d_date_key < today` | offer_status |
| e_sfmc_customer_daily_ss | Incremental | `d_date_key < today` | wallet_type, source |

## Key Concept: Compare What Should NOT Change

| Table Type | What to Compare | Why |
|------------|-----------------|-----|
| SCD2 | Current records distribution | Historical records are immutable |
| Snapshot | Past dates only | Today's data still changing |
| Incremental | Past dates only | New dates expected to grow |

## Thresholds

| Status | Variance |
|--------|----------|
| PASS | < 0.1% |
| WARN | 0.1% - 1% |
| FAIL | > 1% |

## Environment

- **Dev/UAT**: Allowed
- **Prod**: Blocked (macro will error)

## Storage

Tables created by `regression_init()`:
- `work.zzmy_qa_regression_baseline`
- `work.zzmy_qa_regression_results`
