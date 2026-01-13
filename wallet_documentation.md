# Wallet System Documentation

## Overview

Wallet is a **customer loyalty and rewards program** for One NZ (Vodafone). The system manages promotional balances that customers earn through campaigns and redeem for discounts on services, devices, or trade-in value.

**Key capabilities:**
- Track customer wallet balances across multiple campaigns
- Manage wallet lifecycle (creation, updates, suspension, deletion)
- Send customer data to YouTap (wallet application backend)
- Receive balance snapshots and events from YouTap
- Generate analytics and reports for business teams
- Export data to SFMC for marketing campaigns

---

## Key Concepts

### Wallet Types

| Type | Source | Description |
|------|--------|-------------|
| **ON-ACCOUNT** | Siebel/PDB | Postpay mobile customers with billing accounts |
| **PREPAY** | MATRIX | Prepay mobile customers |
| **NON-CUSTOMER** | Microsite/Dosh | Non-customers who signed up via web or partner |

### Wallet Identifiers

| ID | Description | Scope |
|----|-------------|-------|
| `wallet_id` | MSISDN (phone number) starting with '64' | Can change (MSISDN change) |
| `wallet_member_key` | MD5 hash of wallet_id + billing_account_number | Consistent across wallet versions |
| `wallet_customer_key` | MD5 hash of wallet_member_key + timestamp | Unique per SCD2 version |
| `billing_account_number` | BAN from Siebel (OA) or generated P-number (PP) | Links to billing system |

### Balance States

> Wallet balances represent **reward values (points / vouchers)**, **not real cash**.  
> They follow a **reward lifecycle model**.  
> **Redeemed events** are the primary source for financial reconciliation.

| State | Meaning |
|------|--------|
| `balance_earned` | Reward value earned by the customer. |
| `balance_available` | Reward value the customer is allowed to use, subject to rules. |
| `balance_redeemed` | Reward value successfully used. |
| `balance_expired` | Reward value expired before use. |
| `balance_void` | Reward value cancelled or invalidated. |
| `balance_transferred_from` / `balance_transferred_to` | Reward value moved between wallets. |

#### QA Note
- Balances are not cash-equivalent.
- **Redeemed** is the key metric for reconciliation.
- Earned and available reflect lifecycle states.


### Wallet Eligibility

A wallet is eligible (`wallet_eligibility_flag = 'Y'`) when:
- `current_record_ind = 1` (current version)
- `service_status_name` is NOT 'Wallet Deleted'
- `wallet_delete_flag = 'N'`

---

## System Architecture

### Data Flow

```
                         SOURCE SYSTEMS
    ┌──────────────────────────────────────────────────────┐
    │  Siebel/PDB      │  MATRIX       │  Microsite/Dosh   │
    │  (ON-ACCOUNT)    │  (PREPAY)     │  (NON-CUSTOMER)   │
    │  ds_pdb_service  │  ds_mtx_sub_  │  ds_grav_non_     │
    │  ds_pdb_billing  │  subscriber   │  customer         │
    │  _account        │               │  ds_dosh_non_     │
    │                  │               │  customer         │
    └──────────────────────────────────────────────────────┘
                                │
                                ▼
                 ┌──────────────────────────┐
                 │  ds_yt_wallet_management  │  ← MASTER TABLE
                 │  (wallet lifecycle logic) │
                 └──────────────────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            ▼                   ▼                   ▼
     ┌─────────────┐    ┌─────────────┐    ┌────────────────┐
     │ds_yt_wallet │    │ds_yt_wallet │    │ds_yt_wallet_   │
     │_customer    │    │_scores      │    │non_customer    │
     └─────────────┘    └─────────────┘    └────────────────┘
            │                   │                   │
            └───────────────────┼───────────────────┘
                                ▼
                 ┌──────────────────────────┐
                 │    OUTBOUND TO YOUTAP     │
                 │    (AWS S3 files)         │
                 │    e_yt_wallet_customer   │
                 │    e_yt_wallet_scores     │
                 │    e_yt_wallet_non_cust   │
                 └──────────────────────────┘
                                │
                                ▼
                 ┌──────────────────────────┐
                 │        YOUTAP APP         │
                 │   (wallet application)    │
                 └──────────────────────────┘
                                │
                                ▼
                 ┌──────────────────────────┐
                 │   INBOUND FROM YOUTAP    │
                 │   ds_yt_business_events  │  ← events (earn, redeem, etc.)
                 │   ds_yt_daily_snapshot   │  ← daily balance per campaign
                 └──────────────────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            ▼                   ▼                   ▼
     ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
     │f_wallet_    │    │ds_002_*     │    │e_sfmc_*     │
     │financial_   │    │ds_008_*     │    │(to SFMC)    │
     │monthly      │    │ds_010_*     │    │             │
     │             │    │ds_011_*     │    │             │
     └─────────────┘    └─────────────┘    └─────────────┘
           │                   │                   │
           └───────────────────┼───────────────────┘
                               ▼
                 ┌──────────────────────────┐
                 │      POWER BI / SFMC      │
                 │      (reporting)          │
                 └──────────────────────────┘
```

### Integration Points

| System | Direction | Tables | Purpose |
|--------|-----------|--------|---------|
| Siebel/PDB | Inbound | ds_pdb_customer, ds_pdb_billing_account, ds_pdb_service | Customer & service data |
| MATRIX | Inbound | ds_mtx_sub_subscriber | Prepay subscriber data |
| YouTap | Outbound | e_yt_wallet_customer, e_yt_wallet_scores, e_yt_wallet_non_customer | Wallet data for app |
| YouTap | Inbound | ds_yt_business_events, ds_yt_daily_snapshot | Events & balances |
| SFMC | Outbound | e_sfmc_customer_daily_ss, e_sfmc_offer_daily_ss | Marketing data |
| ML Store | Inbound | wallet_service_*_fact | Churn, CLV, propensity scores |

---

## Core Tables

### Master Tables

| Table | Layer | Purpose |
|-------|-------|---------|
| `ds_yt_wallet_management` | refined | **Master lifecycle table** - determines wallet type, status, action, eligibility |
| `ds_yt_wallet_customer` | modelled | Customer wallet data sent to YouTap |
| `ds_yt_wallet_scores` | modelled | ML scores per wallet (churn, CLV, IFP propensity) |
| `ds_yt_wallet_non_customer` | modelled | Non-customer wallets (microsite/Dosh) |

### Inbound Tables (from YouTap)

| Table | Layer | Purpose |
|-------|-------|---------|
| `ds_yt_business_events` | refined | All wallet events (earn, redeem, expire, transfer, etc.) |
| `ds_yt_daily_snapshot` | refined | Daily balance snapshot per wallet/campaign |

### Analytics Tables

| Table | Purpose |
|-------|---------|
| `f_wallet_financial_monthly` | Monthly opening/closing balances with expiry buckets |
| `ds_002_wallet_balances` | Balance aggregations at 4 grains (ALL, CAMPAIGN, COHORT, TOTAL) |
| `ds_002_okr_balance` | OKR metrics for balance |
| `ds_002_wallet_deactivations` | Wallet deactivation tracking |
| `ds_008_ifp_campaign_analysis` | IFP campaign performance |
| `ds_010_ga_wallet_access_analysis` | Google Analytics wallet app usage |
| `ds_011_ifp_upsell_crossell` | Upsell/cross-sell analysis |

### Outbound Tables

| Table | Destination | Purpose |
|-------|-------------|---------|
| `e_yt_wallet_customer` | YouTap (AWS) | Customer wallet attributes |
| `e_yt_wallet_scores` | YouTap (AWS) | ML scores |
| `e_yt_wallet_non_customer` | YouTap (AWS) | Non-customer wallets |
| `e_sfmc_customer_daily_ss` | SFMC | Daily customer snapshot for marketing |
| `e_sfmc_offer_daily_ss` | SFMC | Daily offer snapshot for marketing |

---

## Business Rules

### 1. Wallet Type Determination

| Source | wallet_type | Condition |
|--------|-------------|-----------|
| Siebel/PDB | ON-ACCOUNT | `service_type_name = 'mobile - on account'` AND `wallet_id` starts with '64' |
| MATRIX | PREPAY | `status_value IN (31,32,33,34,35)` |
| Microsite | NON-CUSTOMER | `microsite_flag = 'Y'` |
| Dosh | NON-CUSTOMER | `dosh_customer_flag = 'Y'` |

**MATRIX status codes:**
- 31 = ACTIVE
- 32 = NOCREDIT
- 33 = RESTRICT
- 34 = DEACTIVE
- 35 = WELCOME

### 2. Wallet Lifecycle Actions

`ds_yt_wallet_management` sets the `action` field based on wallet state changes:

**New Wallet:**
| Action | Trigger |
|--------|---------|
| `OA_NEW` | New MSISDN in Siebel with active service |
| `PP_NEW` | New MSISDN in MATRIX with non-DEACTIVE status |
| `NC_NEW` | New wallet from microsite or Dosh |

**Type Transitions:**
| Action | Trigger |
|--------|---------|
| `PP_2_OA` | PREPAY MSISDN appears in OA data as active |
| `OA_2_PP` | ON-ACCOUNT MSISDN appears in PP data, not in OA |
| `NC_2_OA` | NON-CUSTOMER MSISDN appears in OA data |
| `NC_2_PP` | NON-CUSTOMER MSISDN appears in PP data |
| `OFFNET_NC_2_OA` | Off-net NC wallet matches OA data |
| `OFFNET_NC_2_PP` | Off-net NC wallet matches PP data |

**Updates:**
| Action | Trigger |
|--------|---------|
| `OA_UPDATE` | OA plan or status changed |
| `PP_UPDATE` | PP plan or status changed |
| `NC_UPDATE` | NC temp_msisdn changed |
| `OA_MSISDN_CHANGE` | Same customer, different MSISDN |
| `OA_MSISDN_CHANGE_MICROSITE` | MSISDN change via microsite temp MSISDN |

**Suspension:**
| Action | Trigger |
|--------|---------|
| `OA_SUSPEND_DEACTIVE` | OA service status = deactivated |
| `OA_SUSPEND_DELETED` | OA service disappeared from Siebel |
| `PP_SUSPEND_DEACTIVE` | PP status = DEACTIVE |
| `PP_SUSPEND_DELETED` | PP disappeared from MATRIX |
| `NC_SUSPEND` | NC wallet past suspend threshold |

**Deletion:**
| Action | Trigger |
|--------|---------|
| `WALLET_DELETED` | `wallet_delete_date <= CURRENT_DATE()` |
| `WALLET_DELETED_MSISDN_CHANGE` | Old MSISDN deleted due to MSISDN change |

**Recycle (MSISDN reuse):**
| Action | Trigger |
|--------|---------|
| `PP_RECYCLED` | Previously deleted PP MSISDN reappears as active |
| `OA_RECYCLED` | Previously deleted OA wallet reactivated |

### 3. Delete Date Rules

Controlled by `meta.lcf_control`:

| Key | Purpose |
|-----|---------|
| `WFE_OA_PP_DELETE_DAYS` | Days until suspended OA/PP wallet is deleted (~90) |
| `WFE_NC_DELETE_DAYS` | Days until NC wallet is deleted (~30) |
| `WFE_SUSPEND_DAYS` | Days until suspended wallet moves to NC_SUSPEND (~14) |
| `WFE_TEMP_MSISDN_VALID` | Days temp MSISDNs remain valid for matching |

**Exceptions:**
- Dosh customers: `wallet_delete_date = NULL` (never auto-delete)
- Trade-In: Balance counts as available even if offer_status = 'expired'/'deleted'

### 4. Giveaway Amount Assignment

Initial balance assigned via `giveaway_amount()` macro:

**Eligibility:**
- `wallet_eligibility_flag = 'Y'`
- `giveaway_amount = 0` (not already assigned)
- `microsite_flag = 'N'` (customers only)

**Strategy (from `WFE_GIVEAWAY_TYPE`):**
- `INITIAL`: Rule-based assignment by plan/segment
- `RANDOM`: Probability-weighted assignment from `meta.lcf_giveaway`

### 5. Balance Calculations

**Total balance:**
```sql
total_available_earned = SUM(balance_available) + SUM(balance_earned)
```

**Trade-In exception:**
```sql
-- Count as available even if expired/deleted for trade-in campaigns
WHERE balance_available > 0
   OR (LOWER(campaign_type) = 'trade-in'
       AND LOWER(offer_status) NOT IN ('expired', 'deleted'))
```

**Monthly financial:**
- Opening balance = balance on first day of month
- Closing balance = balance on first day of next month
- Movement = earned, redeemed, expired, voided during month

---

## Technical Patterns

### Incremental Strategies

| Table | Strategy | Key Logic |
|-------|----------|-----------|
| `ds_yt_wallet_management` | MERGE (SCD2) | Update old record end_date, insert new version |
| `ds_yt_business_events` | APPEND + dedup | Append new, delete duplicates in last 5 days |
| `ds_yt_daily_snapshot` | APPEND | Append by snapshot_date |
| `ds_002_*` | APPEND | Append by cal_date |
| `f_wallet_financial_monthly` | APPEND | Append by month |

### SCD Type 2 Pattern

For `ds_yt_wallet_management`, `ds_yt_wallet_customer`, `ds_yt_wallet_scores`:

```sql
-- Key columns
wallet_management_key    -- unique per version (PK)
wallet_member_key        -- consistent across versions
version_no               -- increments on change
current_record_ind       -- 1 = current, 0 = historical
record_start_date_time   -- when version became active
record_end_date_time     -- when version ended ('9999-12-31' if current)
```

**On change:**
1. Old record: `current_record_ind = 0`, `record_end_date_time = NOW()`
2. New record: `current_record_ind = 1`, `version_no++`, `record_start_date_time = NOW()`

### Key Join Patterns

**Current record only:**
```sql
WHERE current_record_ind = 1
```

**Temporal join (point-in-time):**
```sql
WHERE snapshot_date BETWEEN record_start_date_time AND record_end_date_time
```

**Wallet member key join:**
```sql
-- Consistent ID across versions
ON s.d_wallet_member_key = c.wallet_member_key
```

---

## Configuration

### Control Parameters (meta.lcf_control)

| Key | Purpose |
|-----|---------|
| `WFE_OA_PP_DELETE_DAYS` | Days before suspended OA/PP deleted |
| `WFE_NC_DELETE_DAYS` | Days before NC deleted |
| `WFE_SUSPEND_DAYS` | Days before suspended → NC_SUSPEND |
| `WFE_TEMP_MSISDN_VALID` | Days temp MSISDNs stay valid |
| `WFE_GIVEAWAY_TYPE` | INITIAL or RANDOM |

### Giveaway Configuration (meta.lcf_giveaway)

| Column | Purpose |
|--------|---------|
| `wallet_type` | CUSTOMER, NON-CUSTOMER |
| `amount` | Giveaway amount (cents) |
| `weight` | Probability weight for RANDOM |
| `valid_from` / `valid_to` | Date range |

### Device Offer Configuration (meta.lcf_device_offer)

| Column | Purpose |
|--------|---------|
| `low_amount` / `high_amount` | Balance range |
| `device_offer` | Offer tier name |
| `valid_from` / `valid_to` | Date range |

---

## Common Tasks

### Adding a New Action Type

1. Create CTE in `ds_yt_wallet_management.sql`:
```sql
new_action AS (
  SELECT wallet_id, billing_account_number, wallet_member_key,
         'NEW_ACTION' AS action,
         ...
  FROM {{ this }} t
  WHERE <conditions>
)
```
2. Add to final UNION with appropriate `_order`
3. Test with sample data
4. Update downstream tables if needed

### Adding a New Customer Attribute

1. Add to source: `ss_yt_wallet_customer` (snapshot)
2. Add to `s_yt_wallet_customer_current` (work view)
3. Add to `ds_yt_wallet_customer` SELECT
4. Add to `e_yt_wallet_customer` for outbound
5. Update SFMC tables if attribute needed for marketing

### Adding a New Analytics Model

1. Create `models/wallet/modelled/ds_0XX_new_model.sql`
2. Use incremental append pattern:
```sql
{{ config(
    materialized = 'incremental',
    incremental_strategy = 'append'
) }}
```
3. Join to `ds_yt_wallet_daily_ss` for balance data
4. Join to `ds_yt_wallet_customer` for customer attributes
5. Create Power BI view in `models/wallet/powerbi/`

### Debugging Wallet Issues

**Check current wallet state:**
```sql
SELECT * FROM modelled.ds_yt_wallet_management
WHERE wallet_id = '64xxxxxxxxx'
AND current_record_ind = 1
```

**Check wallet history:**
```sql
SELECT * FROM modelled.ds_yt_wallet_management
WHERE wallet_id = '64xxxxxxxxx'
ORDER BY version_no
```

**Check balance:**
```sql
SELECT * FROM refined.ds_yt_daily_snapshot
WHERE wallet_id = '64xxxxxxxxx'
AND snapshot_date = (SELECT MAX(snapshot_date) FROM refined.ds_yt_daily_snapshot)
```

**Check events:**
```sql
SELECT * FROM refined.ds_yt_business_events
WHERE wallet_id = '64xxxxxxxxx'
ORDER BY event_timestamp DESC
LIMIT 100
```

---

## Glossary

| Term | Definition |
|------|------------|
| BAN | Billing Account Number |
| CLV | Customer Lifetime Value |
| IFP | In-Flight Purchase (device finance) |
| MSISDN | Mobile phone number (wallet_id) |
| NC | Non-Customer |
| OA | On-Account (postpay) |
| PP | Prepay |
| SCD2 | Slowly Changing Dimension Type 2 |
| SFMC | Salesforce Marketing Cloud |
| WFE | Wallet Front-End |
| WMK | Wallet Member Key |
| YT | YouTap |
