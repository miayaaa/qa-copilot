# Wallet Domain Context

## Overview

**Wallet** is a loyalty rewards system that tracks customer points, vouchers, and redemption activities. It integrates with YouTap as the external rewards platform and connects to multiple source systems (Siebel/PDB for on-account, Matrixx for prepay, Microsite/Dosh for non-customers).

**Business Purpose:**
- Reward customers for spending and engagement
- Track point earning, redemption, expiry, and transfers
- Support marketing campaigns and customer retention

**Data Flow:** Source systems → Wallet Management (master) → YouTap (outbound) → Events/Snapshots (inbound) → Analytics/Reporting

---

> **Domain context for QA SQL Mentor** (wallet-related tables only)
> Applies to: General QA, Feature Testing, Regression Testing.
> For migration-specific context, see [MIGRATION.md](MIGRATION.md).

## Table of Contents

- [Key Identifiers](#key-identifiers)
- [Core Tables](#core-tables)
- [Data Flow](#data-flow)
- [Business Rules](#business-rules)
- [Balance States](#balance-states)
- [Common Joins and Filters](#common-joins-and-filters)
- [SCD2 Pattern](#scd2-pattern)
- [Testing Blind Spots](#testing-blind-spots)
- [Glossary](#glossary)

---

## Key Identifiers

| ID | Column | Description | Scope |
|----|--------|-------------|-------|
| wallet_id | WALLET_ID | MSISDN (phone number) starting with '64' | Can change |
| wallet_member_key | WALLET_MEMBER_KEY | MD5(wallet_id + BAN) | **Consistent across versions - use for joins** |
| wallet_customer_key | WALLET_CUSTOMER_KEY | MD5(wallet_member_key + timestamp) | Unique per SCD2 version |
| billing_account_number | BILLING_ACCOUNT_NUMBER | BAN from Siebel (OA) or P-number (PP) | Links to billing |

**QA Join Pattern:**
```sql
-- Always use wallet_member_key for cross-table joins
ON a.WALLET_MEMBER_KEY = b.WALLET_MEMBER_KEY
WHERE a.CURRENT_RECORD_IND = 1
  AND b.CURRENT_RECORD_IND = 1
```

---

## Core Tables

### Wallet Lifecycle (Authoritative)

| Table | Purpose | Grain |
|-------|---------|-------|
| ds_yt_wallet_management | Master lifecycle - type, status, action, eligibility | wallet_member_key |
| ds_yt_wallet_customer | Customer wallet data to YouTap | wallet_member_key |
| ds_yt_wallet_scores | ML scores (churn, CLV, IFP) | wallet_member_key |
| ds_yt_wallet_non_customer | Non-customer wallets | wallet_member_key |

### Inbound (from YouTap)

| Table | Purpose |
|-------|---------|
| ds_yt_business_events | All events (earn, redeem, expire, transfer) |
| ds_yt_daily_snapshot | Daily balance per wallet/campaign |

### Analytics

| Table | Purpose |
|-------|---------|
| f_wallet_financial_monthly | Monthly opening/closing balances |
| ds_002_wallet_balances | Balance aggregations (ALL, CAMPAIGN, COHORT, TOTAL) |

### Key Sources

| Source | Tables |
|--------|--------|
| PDB (on-account) | ds_pdb_service, ds_pdb_customer, ds_pdb_billing_account |
| Matrixx (prepay) | ds_mtx_sub_subscriber |
| Non-customer feeds | ds_grav_non_customer, ds_dosh_non_customer |
| Partner Dosh | ds_dosh_transactions |
| Meta control | meta.lcf_control |

---

## Data Flow

```
SOURCE SYSTEMS
├── Siebel/PDB (ON-ACCOUNT) → ds_pdb_*
├── MATRIX (PREPAY) → ds_mtx_*
└── Microsite/Dosh (NON-CUSTOMER) → ds_grav_*, ds_dosh_*
            │
            ▼
    ds_yt_wallet_management (MASTER - lifecycle logic)
            │
    ┌───────┼───────┐
    ▼       ▼       ▼
ds_yt_    ds_yt_   ds_yt_wallet_
wallet_   wallet_  non_customer
customer  scores
    │       │       │
    └───────┼───────┘
            ▼
    OUTBOUND TO YOUTAP (AWS S3)
    e_yt_wallet_customer, e_yt_wallet_scores
            │
            ▼
    INBOUND FROM YOUTAP
    ds_yt_business_events (events)
    ds_yt_daily_snapshot (balances)
            │
            ▼
    ANALYTICS & REPORTING
    f_wallet_financial_monthly, ds_002_*, Power BI
```

---

## Business Rules

### Wallet Types

| Type | Source | Condition |
|------|--------|-----------|
| ON-ACCOUNT (OA) | Siebel/PDB | service_type_name = 'Mobile - On Account' AND wallet_id starts '64' |
| PREPAY (PP) | MATRIX | status_value IN (31,32,33,34,35) |
| NON-CUSTOMER (NC) | Microsite/Dosh | microsite_flag = 'Y' OR dosh_customer_flag = 'Y' |

### Prepay Status Codes (Matrixx)

| Code | Status |
|------|--------|
| 31 | ACTIVE |
| 32 | NOCREDIT |
| 33 | RESTRICT |
| 34 | DEACTIVE |
| 35 | WELCOME |

### Wallet Eligibility

A wallet is eligible (`wallet_eligibility_flag = 'Y'`) when:
- `current_record_ind = 1`
- `service_status_name` NOT 'Wallet Deleted'
- `wallet_delete_flag = 'N'`

### Lifecycle Actions

| Action | Meaning |
|--------|---------|
| OA_NEW, PP_NEW, NC_NEW | New wallet created |
| PP_2_OA, OA_2_PP | Type transition |
| OA_UPDATE, PP_UPDATE | Attribute changed |
| OA_SUSPEND_*, PP_SUSPEND_* | Wallet suspended |
| WALLET_DELETED | Wallet deleted |
| PP_RECYCLED, OA_RECYCLED | MSISDN reused |
| DOSH_NEW_CUSTOMER | Dosh partner activation |
| MSISDN_CHANGE | Phone number changed |

### Control Parameters (meta.lcf_control)

| Parameter | Days | Purpose |
|-----------|------|---------|
| WFE_OA_PP_DELETE_DAYS | ~90 | Days until suspended OA/PP deleted |
| WFE_NC_DELETE_DAYS | ~30 | Days until NC deleted |
| WFE_SUSPEND_DAYS | ~14 | Days until NC_SUSPEND |
| WFE_TEMP_MSISDN_VALID | - | Temp MSISDN validity window |

**Exception:** Dosh customers have `wallet_delete_date = NULL` (never auto-delete)

### Priority Logic

- If OA and PP both active for same MSISDN, **OA wins** (PP_NEW suppressed)
- NC is suppressed when an eligible OA/PP exists for same MSISDN

### Dosh-Specific Rules

| Event | Action |
|-------|--------|
| DOSH_NEW_CUSTOMER | Clear delete_date, set dosh_customer_flag = 'Y' |
| ACCOUNT_SUSPENDED | Set delete_date for NC, dosh_customer_flag = 'N' |
| MSISDN_CHANGE | Update wallet_id, hard-delete conflicting wallet |

---

## Balance States

Balances are **reward values (points/vouchers)**, NOT real cash.

| State | Meaning |
|-------|---------|
| `balance_available` | Potential reward value. Triggered when an offer is Saved or received. This is "shadow money" (not yet spendable). |
| `balance_earned` | Actual spendable balance. The reward has been confirmed and can be redeemed |                                  | `balance_redeemed` | Reward value successfully used (**reconciliation metric**) |
| `balance_expired` | Reward value expired before use |
| `balance_void` | Reward value cancelled or invalidated |
| `balance_transferred_from/to` | Reward value moved between wallets |

**Trade-in Exception:** Zero balance with active offer (offer_status not in expired/deleted) still counts as available.

---

## Common Joins and Filters

### Standard Filters

| Context | Filter |
|---------|--------|
| Current SCD record | `CURRENT_RECORD_IND = 1` |
| Active PDB service | `current_record_ind = 1 AND service_current_record_ind = 1 AND service_status_name = 'Active'` |
| Latest Matrixx day | `DATE_TRUNC('DAY', sub_extract_date) = (SELECT MAX(...))` |
| Exclude deleted wallets | `wallet_delete_flag = 'N' AND LOWER(service_status_name) != 'wallet deleted'` |

### Common Joins

| Join | Pattern |
|------|---------|
| Wallet management to PDB (OA) | `m.wallet_id = s.service_id AND m.wallet_type = 'ON-ACCOUNT'` |
| Wallet management to Matrixx (PP) | `m.wallet_id = mtx.external_id` |
| Daily snapshot to wallet customer | `ds_yt_wallet_daily_ss.d_wallet_customer_key = d_wallet_customer.d_wallet_customer_key` |
| Snapshot to campaign (temporal) | `snapshot_date BETWEEN d_campaign.record_start_date_time AND record_end_date_time` |

---

## SCD2 Pattern

All wallet tables use Slowly Changing Dimension Type 2:

| Column | Purpose |
|--------|---------|
| *_key (e.g. WALLET_SCORE_KEY) | Unique per version (PK) |
| WALLET_MEMBER_KEY | Consistent across versions (grain) |
| VERSION_NO | Increments on change |
| CURRENT_RECORD_IND | 1 = current, 0 = historical |
| RECORD_START_DATE_TIME | When version became active |
| RECORD_END_DATE_TIME | When version ended ('9999-12-31' if current) |

**QA Rule:** Always filter `CURRENT_RECORD_IND = 1` unless checking history.

---

## Testing Blind Spots

High-risk areas to focus on during Feature Testing and Regression:

| # | Risk Area | What Can Go Wrong | Test Focus |
|---|-----------|-------------------|------------|
| 1 | Temporal SCD overlaps | Multiple actions on same day require millisecond ordering | Check for duplicate current_record_ind = 1 per grain |
| 2 | OA/PP dual-active priority | x2_active suppression of PP_NEW | Check no dual wallet_type for same MSISDN |
| 3 | MSISDN change edge cases | temp_msisdn validity and delete/restore logic | Verify wallet_id updates correctly |
| 4 | Recycled MSISDN + BAN changes | Same MSISDN, different BAN creates new wallet_member_key | Check version_no gaps, identity stitching |
| 5 | Dosh processing flags | lcf_processed_flag = 'N' and run_started_at gate | Check no duplicate processing |
| 6 | Snapshot backfill | Incremental loads by lcf_load_timestamp, not snapshot_date | Check for missed late-arriving snapshots |
| 7 | Trade-in balance counting | Special handling for trade-in offers with zero balance | Verify available-wallet metrics |
| 8 | Event deduplication | Post-hook deletes dupes by business_event_key in last 5 days | Check no duplicates outside window |

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
| WMK | Wallet Member Key |
| YT | YouTap |
