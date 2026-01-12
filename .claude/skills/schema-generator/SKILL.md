---
name: schema-generator
description: Generate table schema JSON from column names or business context
---

# Schema Generator

Generate table schema JSON for QA Copilot.

## Output Format

```json
{
  "table_name": "SCHEMA.TABLE_NAME",
  "table_grain": "unique_row_identifier",
  "description": "Business purpose",
  "data_architecture": {
    "grain_definition": "What makes a row unique",
    "primary_key": "pk_column",
    "natural_key": "nk_column"
  },
  "columns": {
    "Logical_Group": {
      "column_name": {"type": "VARCHAR", "desc": "Description"}
    }
  }
}
```

## Type Inference

| Pattern | Type |
|---------|------|
| *_id, *_key | VARCHAR |
| *_date | DATE |
| *_flag, *_ind | VARCHAR, enum: ["Y", "N"] |
| *_count | INT |
| *_amount, *_value | NUMERIC |

## Telecom Domain Knowledge

Common entity relationships:
- **Customer** has many **Accounts**
- **Account** has many **Services** (mobile, broadband, etc.)
- **Service** linked to **Device** and **Plan**
- **Wallet** ties to **Customer** for loyalty/rewards

Join keys typically: `Customer_Key`, `Account_Number`, `Service_Key`, `Wallet_Member_Key`

## Reference Table Usage

When provided, extract:
1. Matching column patterns (type, desc)
2. Business rules to inherit
3. Join keys for relationships

## Rules

- Group columns by business logic (not fixed categories)
- Mark `"pii": "YES"` for personal data
- Keep descriptions under 80 chars
- Preserve exact column names as provided
