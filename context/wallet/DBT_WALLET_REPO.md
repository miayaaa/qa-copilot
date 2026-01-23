# dbt_wallet_aws Repo Reference

> **Source:** `D:\Mia\Repos\dbt_wallet_aws_0116`
> **Last updated:** 2025-01-19

## Models Directory Structure

```
models/
├── gravity/inbound/refined/
│   └── ds_grav_non_customer.sql
├── partners/
│   ├── common/refined/
│   │   ├── ds_partner_campaign_wallets.sql
│   │   └── ds_partner_code_wallets.sql
│   ├── dosh/inbound/refined/
│   │   ├── ds_dosh_non_customer.sql
│   │   └── ds_dosh_transactions.sql
│   └── samsung/inbound/refined/
│       └── ds_sam_campaign_wd.sql
├── sfmc/
│   ├── inbound/refined/
│   │   └── ds_sfmc_spacex.sql
│   └── outbound/serving/
│       ├── e_sfmc_customer_daily_ss.sql
│       └── e_sfmc_offer_daily_ss.sql
├── smoketest/youtap/
│   ├── ds_yt_wallet_customer_st.sql
│   ├── ds_yt_wallet_scores_st.sql
│   ├── e_yt_wallet_customer_st.sql
│   ├── e_yt_wallet_non_customer_st.sql
│   └── e_yt_wallet_scores_st.sql
├── test_mode/
│   ├── l_ml_prop_scores_tm.sql
│   ├── l_pdb_bill_activity_daily_ss_tm.sql
│   ├── l_pdb_billing_account_tm.sql
│   ├── l_pdb_customer_tm.sql
│   └── l_pdb_service_tm.sql
├── wallet/
│   ├── modelled/
│   │   ├── d_*.sql (dimensions: billing_account, campaign, customer, date, etc.)
│   │   ├── ds_*.sql (datasets: wallet_balances, okr_*, yt_event_recon, etc.)
│   │   └── f_*.sql (facts: business_events, ga_page_view, ifp_sales_transaction)
│   ├── powerbi/
│   │   └── v_*.sql (views for PowerBI dashboards)
│   ├── raw/
│   │   └── l_*.sql (landing tables from sources)
│   ├── refined/
│   │   └── ds_*.sql (refined datasets)
│   ├── serving/
│   │   └── v_*.sql (serving views)
│   └── work/
│       └── s_*.sql (staging/work tables)
├── youtap/
│   ├── inbound/refined/
│   │   ├── ds_yt_business_events.sql
│   │   ├── ds_yt_daily_snapshot.sql
│   │   └── ds_yt_survey_response.sql
│   └── outbound/
│       ├── modelled/
│       │   ├── ds_yt_wallet_customer.sql
│       │   ├── ds_yt_wallet_non_customer.sql
│       │   └── ds_yt_wallet_scores.sql
│       ├── refined/
│       │   └── ds_yt_wallet_management.sql
│       ├── serving/
│       │   ├── e_yt_wallet_customer.sql
│       │   ├── e_yt_wallet_non_customer.sql
│       │   └── e_yt_wallet_scores.sql
│       └── work/
│           └── s_yt_*.sql (staging tables)
└── *.yml (schema definitions)
```

## Schema YAML Files

| File | Purpose |
|------|---------|
| sources.yml | External source definitions |
| raw.yml | Landing table schemas |
| refined.yml | Refined dataset schemas |
| modelled.yml | Modelled table schemas |
| serving.yml | Serving layer schemas |
| work.yml | Work/staging schemas |

## Data Sources (from sources.yml)

| Source Name | Database | Schema | Key Tables |
|-------------|----------|--------|------------|
| pdb_modelled | dxpdb_prod | modelled | d_customer, d_billing_account, d_service, f_bill_activity_daily_snapshot |
| ml_store | prod_ml_store | serving | wallet_service_classification_propensity_score_fact, wallet_service_lifetime_value_fact |
| prod_modelled | prod | modelled | d_date, d_ifp |
| youtap | DBT_TARGET_DB | raw | l_yt_business_events, ex_yt_snapshot |
| meta | DBT_TARGET_DB | meta | lcf_eligibility_bypass, lcf_partner_codes, lcf_control |
| matrixx | prod_matrixx | refined | ds_mtx_prepay_sub_subscriber |
| ga_prod | prod_google_analytics | raw | analytics views |
| sfmc | DBT_TARGET_DB | raw | l_sfmc_spacex |
| grav | DBT_TARGET_DB | raw | l_grav_non_customer |
| dosh | DBT_TARGET_DB | raw | l_dosh_non_customer, l_dosh_transactions |

## Layer Naming Convention

| Prefix | Layer | Description |
|--------|-------|-------------|
| l_ | raw | Landing tables (source extracts) |
| ds_ | refined/modelled | Datasets (transformed) |
| d_ | modelled | Dimension tables |
| f_ | modelled | Fact tables |
| s_ | work | Staging/intermediate |
| e_ | serving | Extract/export tables |
| v_ | serving | Views |

## Key Tables for Migration QA

### Core Wallet Tables

| Table | Path | Type | Key Columns |
|-------|------|------|-------------|
| **ds_yt_wallet_management** | youtap/outbound/refined/ | SCD2 incremental | wallet_management_key, wallet_member_key, action, wallet_type |
| ds_yt_wallet_customer | youtap/outbound/modelled/ | SCD2 | wallet_member_key, current_record_ind, version_no |
| ds_yt_wallet_daily_ss | wallet/modelled/ | daily snapshot | d_date_key, d_wallet_member_key |
| e_yt_wallet_customer | youtap/outbound/serving/ | extract | wallet_member_key |

### SFMC Tables

| Table | Path | Type | Key Columns |
|-------|------|------|-------------|
| e_sfmc_customer_daily_ss | sfmc/outbound/serving/ | incremental append | e_sfmc_customer_daily_ss_key, d_date_key, wallet_balance_* |
| e_sfmc_offer_daily_ss | sfmc/outbound/serving/ | incremental append | e_sfmc_offer_daily_ss_key |

### Report/Analytics Tables (ds_00x series)

| Table | Path | Purpose |
|-------|------|---------|
| ds_002_wallet_balances | wallet/modelled/ | Wallet balance aggregations |
| ds_002_wallet_deactivations | wallet/modelled/ | Wallet deactivation tracking |
| ds_002_okr_balance | wallet/modelled/ | OKR balance metrics |
| ds_008_ifp_campaign_analysis | wallet/modelled/ | IFP campaign analysis |
| ds_010_ga_wallet_access_analysis | wallet/modelled/ | GA wallet access analysis |
| ds_010_ga_wallet_access_analysis_daily | wallet/modelled/ | Daily GA analysis |
| ds_011_ifp_upsell_crossell | wallet/modelled/ | IFP upsell/cross-sell |
| ds_012_dosh_recon_daily | wallet/modelled/ | Dosh daily reconciliation |

---

## Wallet State Management (ds_yt_wallet_management)

> **Critical table for understanding wallet lifecycle**

### Wallet Types

| Type | Description | Source |
|------|-------------|--------|
| ON-ACCOUNT (OA) | Contract customers | Siebel/PDB (ds_pdb_service) |
| PREPAY (PP) | Prepaid customers | Matrixx (ds_mtx_sub_subscriber) |
| NON-CUSTOMER (NC) | Non-customers | Microsite (ds_grav_non_customer) or Dosh (ds_dosh_non_customer) |

### Wallet Actions (State Transitions)

```
┌─────────────────────────────────────────────────────────────────┐
│                     WALLET LIFECYCLE                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [NEW WALLETS]                                                  │
│    NC_NEW ──────► NON-CUSTOMER (microsite/Dosh signup)          │
│    PP_NEW ──────► PREPAY (new prepaid customer)                 │
│    OA_NEW ──────► ON-ACCOUNT (new contract customer)            │
│                                                                 │
│  [TYPE CONVERSIONS]                                             │
│    NC_2_OA ─────► NON-CUSTOMER → ON-ACCOUNT                     │
│    NC_2_PP ─────► NON-CUSTOMER → PREPAY                         │
│    PP_2_OA ─────► PREPAY → ON-ACCOUNT                           │
│    OA_2_PP ─────► ON-ACCOUNT → PREPAY                           │
│                                                                 │
│  [SUSPENSIONS]                                                  │
│    PP_SUSPEND_DEACTIVE ──► PP suspended (status=DEACTIVE)       │
│    PP_SUSPEND_DELETED ───► PP suspended (not in Matrixx)        │
│    OA_SUSPEND_DEACTIVE ──► OA suspended (status!=Active)        │
│    OA_SUSPEND_DELETED ───► OA suspended (not in PDB)            │
│    NC_SUSPEND ───────────► NC suspended (delete_date reached)   │
│                                                                 │
│  [UPDATES]                                                      │
│    PP_UPDATE ───► Plan/status change (still PP)                 │
│    OA_UPDATE ───► Plan/status change (still OA)                 │
│    NC_UPDATE ───► temp_msisdn change                            │
│    OA_MSISDN_CHANGE ──► MSISDN number changed                   │
│                                                                 │
│  [RECYCLED] (MSISDN reused for new customer)                    │
│    PP_RECYCLED ─► Deleted PP MSISDN reactivated                 │
│    OA_RECYCLED ─► Deleted OA MSISDN reactivated                 │
│                                                                 │
│  [DELETION]                                                     │
│    WALLET_DELETED ──► wallet_delete_date reached                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Key Columns in ds_yt_wallet_management

| Column | Description |
|--------|-------------|
| wallet_management_key | Primary key |
| wallet_member_key | Links to ds_yt_wallet_customer |
| wallet_id | MSISDN (phone number) |
| billing_account_number | BAN |
| wallet_type | ON-ACCOUNT, PREPAY, NON-CUSTOMER |
| action | State transition (see above) |
| wallet_eligibility_flag | Y/N - eligible for wallet features |
| service_status_name | Active, Suspended, Wallet Deleted |
| wallet_suspended_date | When suspended |
| wallet_delete_date | Scheduled deletion date |
| wallet_delete_flag | Y if deleted |
| microsite_flag | Y if from microsite journey |
| dosh_customer_flag | Y if Dosh customer |
| giveaway_amount | Bonus amount for NC |
| current_record_ind | 1 = current record (SCD2) |

### Table Relationships

```
ds_yt_wallet_management (refined)
        │
        │ wallet_member_key
        ▼
ds_yt_wallet_customer (modelled, SCD2)
        │
        │ wallet_member_key + d_date_key
        ▼
ds_yt_wallet_daily_ss (modelled, daily snapshot)
        │
        │ d_wallet_member_key + d_date_key
        ▼
e_sfmc_customer_daily_ss (serving, incremental append)
```

  INPUT (YouTap)              MASTER                    OUTPUT
  ────────────────────────────────────────────────────────────────
  ds_yt_business_events  ──┐
  ds_yt_daily_snapshot   ──┼──► ds_yt_wallet_management ──┬──► e_yt_wallet_customer
                           │         (action, type)       ├──► e_yt_wallet_scores
  Source Systems:          │                              └──► e_yt_wallet_non_customer
  ├─ PDB (OA)        ──────┤
  ├─ Matrixx (PP)    ──────┤
  └─ Grav/Dosh (NC)  ──────┘
