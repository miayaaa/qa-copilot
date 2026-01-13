# Wallet Project Context

> **Quick Reference for QA SQL Mentor**
> This document provides business context for the Wallet loyalty system.
> Use anchors to jump to specific sections.

## Table of Contents
- [QA Priority Metrics](#qa-priority-metrics)
- [Key Identifiers](#key-identifiers)
- [Business Rules](#business-rules)
- [Data Flow](#data-flow)
- [Core Tables](#core-tables)
- [SCD2 Pattern](#scd2-pattern)
- [Glossary](#glossary)

---

## QA Priority Metrics

**Most Important for Migration QA:**

| Priority | Metric | Table | Column(s) | Why Important |
|----------|--------|-------|-----------|---------------|
| P1 | Row Count | All | - | Data completeness |
| P1 | Balance Redeemed | ds_yt_daily_snapshot | balance_redeemed | Financial reconciliation |
| P1 | CLV Amount | ds_yt_wallet_scores | MOB_OA_CONSUM_CLV_AMOUNT | Business value metric |
| P2 | Wallet Eligibility | ds_yt_wallet_customer | wallet_eligibility_flag | Active customer count |
| P2 | Churn Score | ds_yt_wallet_scores | MOB_OA_CONSUM_CHURN_SCORE | ML model accuracy |
| P3 | Category Distribution | All | wallet_type, service_status | Data quality |

**Balance Reconciliation Note:**
- Balances are **reward values (points/vouchers)**, NOT real cash
- **balance_redeemed** is the key metric for financial reconciliation
- balance_earned and balance_available reflect lifecycle states only


**Balance States (Lifecycle):**

| State | Meaning |
|------|--------|
| `balance_earned` | Reward value earned by the customer. |
| `balance_available` | Reward value the customer is allowed to use, subject to rules. |
| `balance_redeemed` | Reward value successfully used (reconciliation metric). |
| `balance_expired` | Reward value expired before use. |
| `balance_void` | Reward value cancelled or invalidated. |
| `balance_transferred_from` / `balance_transferred_to` | Reward value moved between wallets. |


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

## Business Rules

### Wallet Types

| Type | Source | Condition |
|------|--------|-----------|
| ON-ACCOUNT | Siebel/PDB | service_type = 'mobile - on account' AND wallet_id starts '64' |
| PREPAY | MATRIX | status_value IN (31,32,33,34,35) |
| NON-CUSTOMER | Microsite/Dosh | microsite_flag = 'Y' OR dosh_customer_flag = 'Y' |

### Wallet Eligibility

A wallet is eligible (`wallet_eligibility_flag = 'Y'`) when:
- `current_record_ind = 1`
- `service_status_name` NOT 'Wallet Deleted'
- `wallet_delete_flag = 'N'`

### Wallet Lifecycle Actions

| Action | Meaning |
|--------|---------|
| OA_NEW, PP_NEW, NC_NEW | New wallet created |
| PP_2_OA, OA_2_PP | Type transition |
| OA_UPDATE, PP_UPDATE | Attribute changed |
| OA_SUSPEND_*, PP_SUSPEND_* | Wallet suspended |
| WALLET_DELETED | Wallet deleted |
| PP_RECYCLED, OA_RECYCLED | MSISDN reused |

### Delete Date Rules

| Parameter | Days | Purpose |
|-----------|------|---------|
| WFE_OA_PP_DELETE_DAYS | ~90 | Days until suspended OA/PP deleted |
| WFE_NC_DELETE_DAYS | ~30 | Days until NC deleted |
| WFE_SUSPEND_DAYS | ~14 | Days until NC_SUSPEND |

**Exception:** Dosh customers have `wallet_delete_date = NULL` (never auto-delete)

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

## Core Tables

### Master Tables

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
