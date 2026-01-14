# QA Copilot

AI-powered SQL assistant for QA Engineers. Generate schema-aware Snowflake SQL through natural language.

## Features

- **Schema-aware SQL generation** - Reads table definitions, uses exact column names
- **Multiple QA patterns** - Duplicates, NULLs, grain checks, balance validation, SCD2 verification
- **Table type detection** - Auto-applies correct filters for SCD2, Snapshot, Event, Monthly Fact tables
- **Schema generator** - Create table definitions from column names or business context
- **Temp schema support** - Use ad-hoc schemas without saving to files
- **Chat history** - Save and resume QA sessions
- **Project context** - Load domain knowledge for better SQL generation

## Quick Start

```bash
# Install dependencies
pip install streamlit anthropic pyyaml

# Set API key (or enter in UI)
export ANTHROPIC_API_KEY=your-key

# Run
streamlit run app.py
```

## Usage

1. Select tables from sidebar (or generate a temp schema)
2. Ask in natural language: "check for duplicates on wallet_member_key"
3. Get runnable Snowflake SQL + QA notes

### Example Prompts

```
"Find duplicate records by grain"
"Check NULL percentage for all columns"
"Validate SCD2 version distribution"
"Compare row counts between date ranges"
"Show balance_redeemed sum by wallet_type"
```

## Project Structure

```
qa-copilot/
├── app.py                      # Streamlit UI
├── tables/                     # Table schema definitions (.yml)
├── chats/                      # Saved chat sessions
├── context/                    # Project-specific business context
│   └── {project}/PROJECT.md
└── .claude/skills/
    ├── qa-sql-mentor/          # SQL generation skill
    │   ├── SKILL.md
    │   └── REFERENCE.md
    └── schema-generator/       # Schema generation skill
        └── SKILL.md
```

## Adding Tables

Create `tables/YOUR_TABLE.yml`:

```yaml
table_name: "SCHEMA.TABLE_NAME"
project: "your-project"
table_grain: "One row per ..."
description: "Business purpose"
columns:
  Keys:
    ID_COLUMN:
      type: VARCHAR
      desc: "Primary identifier"
  Metrics:
    AMOUNT:
      type: NUMERIC
      desc: "Dollar amount"
```

Or use the **Generate Schema** feature in the sidebar.

## Configuration

| Setting | Location | Purpose |
|---------|----------|---------|
| API Key | Sidebar or `ANTHROPIC_API_KEY` env | Claude API access |
| Tables | `tables/*.yml` | Permanent schema definitions |
| Context | `context/{project}/PROJECT.md` | Domain knowledge per project |

## Limitations

- Read-only SQL generation (no execution)
- Snowflake syntax only
- Human review required before running generated SQL
