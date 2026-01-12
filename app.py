"""
QA Copilot - AI-powered SQL Assistant for QA Engineers
Interactive UI for schema-aware SQL generation with QA mentoring
"""

import os
from pathlib import Path

import streamlit as st
import yaml
from anthropic import Anthropic

# Configuration
TABLES_DIR = Path("tables")
SKILLS_DIR = Path(".claude/skills/qa-sql-mentor")

# --- Data Loading ---

def load_all_schemas() -> dict:
    """Load all YAML schema files and extract table info."""
    schemas = {}
    if TABLES_DIR.exists():
        for yaml_file in TABLES_DIR.glob("*.yml"):
            with open(yaml_file, "r", encoding="utf-8") as f:
                content = yaml.safe_load(f)
                if not content:
                    continue

                # Format A: Single table (new format)
                if "table_name" in content:
                    table_name = content["table_name"]
                    schemas[table_name] = {
                        "source_file": yaml_file.name,
                        "definition": content,
                        "relationships": [],
                        "business_rules": []
                    }

                # Format B: Multiple tables (original format)
                elif "tables" in content:
                    for table in content["tables"]:
                        table_name = table["name"]
                        schemas[table_name] = {
                            "source_file": yaml_file.name,
                            "definition": table,
                            "relationships": content.get("relationships", []),
                            "business_rules": content.get("business_rules", [])
                        }
    return schemas


def load_skill_prompt() -> str:
    """Load the skill prompt from SKILL.md (without frontmatter)."""
    skill_path = SKILLS_DIR / "SKILL.md"
    if skill_path.exists():
        with open(skill_path, "r", encoding="utf-8") as f:
            content = f.read()
            # Remove YAML frontmatter
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    return parts[2].strip()
    return ""


def load_reference() -> str:
    """Load SQL reference patterns."""
    ref_path = SKILLS_DIR / "REFERENCE.md"
    if ref_path.exists():
        with open(ref_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


# --- Prompt Building ---

def format_selected_schema(schemas: dict, selected_tables: list) -> str:
    """Format only selected tables into prompt-ready text."""
    if not selected_tables:
        return "No tables selected."

    parts = []
    included_rules = set()

    for table_name in selected_tables:
        if table_name in schemas:
            info = schemas[table_name]
            parts.append(f"## {table_name}")
            parts.append(f"Source: `{info['source_file']}`\n")
            parts.append(yaml.dump(info["definition"], default_flow_style=False, sort_keys=False))

            # Add relevant relationships
            for rel in info["relationships"]:
                if table_name in rel["from"] or table_name in rel["to"]:
                    parts.append(f"Relationship: {rel['from']} -> {rel['to']} ({rel['type']})")

            # Add business rules (deduplicated)
            for rule in info["business_rules"]:
                rule_key = rule["name"]
                if rule_key not in included_rules:
                    included_rules.add(rule_key)
                    parts.append(f"Business Rule [{rule['name']}]: {rule['description']}")

            parts.append("")

    return "\n".join(parts)


def build_system_prompt(skill_prompt: str, reference: str, schema_text: str) -> list:
    """Build system prompt blocks with caching."""
    return [
        {
            "type": "text",
            "text": f"{skill_prompt}\n\n---\n\n# SQL Reference\n\n{reference}",
            "cache_control": {"type": "ephemeral"}
        },
        {
            "type": "text",
            "text": f"# Selected Tables for QA\n\n{schema_text}"
        }
    ]


# --- Claude API ---

MAX_HISTORY = 20  # messages


def chat_with_claude(client: Anthropic, system_blocks: list, messages: list) -> str:
    """Send chat to Claude and return response."""
    trimmed = messages[-MAX_HISTORY:] if len(messages) > MAX_HISTORY else messages

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=system_blocks,
        messages=trimmed
    )
    return response.content[0].text


# --- Streamlit UI ---

def init_session():
    """Initialize session state."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "selected_tables" not in st.session_state:
        st.session_state.selected_tables = []


def render_message(role: str, content: str):
    """Render a chat message with SQL blocks."""
    with st.chat_message(role):
        st.markdown(content)


def main():
    st.set_page_config(
        page_title="QA Copilot",
        page_icon="🔍",
        layout="wide"
    )

    init_session()

    # Load data
    all_schemas = load_all_schemas()
    skill_prompt = load_skill_prompt()
    reference = load_reference()

    # --- Sidebar ---
    with st.sidebar:
        st.title("🔍 QA Copilot")
        st.caption("AI-powered SQL Assistant")

        st.divider()

        # API Key
        api_key = st.text_input(
            "Claude API Key",
            type="password",
            value=os.getenv("ANTHROPIC_API_KEY", ""),
            help="Enter your Anthropic API key"
        )

        if not api_key:
            st.warning("Please enter API Key")

        st.divider()

        # Table Selection
        st.subheader("📊 Select Tables for QA")

        if all_schemas:
            table_names = list(all_schemas.keys())
            selected = st.multiselect(
                "Select tables (multi-select)",
                options=table_names,
                default=st.session_state.selected_tables or table_names[:1],
                help="AI will generate SQL based on selected schemas"
            )
            st.session_state.selected_tables = selected

            # Show selected table info
            if selected:
                with st.expander(f"{len(selected)} tables selected", expanded=False):
                    for table in selected:
                        info = all_schemas[table]
                        defn = info["definition"]
                        # Count columns (handle both formats)
                        cols = defn.get("columns", {})
                        if isinstance(cols, dict):
                            # New format: grouped columns
                            col_count = sum(len(group) for group in cols.values() if isinstance(group, dict))
                        else:
                            # Old format: list of columns
                            col_count = len(cols)
                        desc = defn.get("description", "")[:60]
                        st.markdown(f"**{table}**")
                        st.caption(f"{col_count} columns | {desc}...")
        else:
            st.info("No schema files found. Add .yml files to tables/ directory")

        st.divider()

        # Clear chat
        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

    # --- Main Chat Area ---
    st.header("💬 Chat")

    if not st.session_state.selected_tables:
        st.info("👈 Please select tables on the left first")
        return

    # Display selected context
    st.caption(f"Current context: {', '.join(st.session_state.selected_tables)}")

    # Chat history
    for msg in st.session_state.messages:
        render_message(msg["role"], msg["content"])

    # Chat input
    if prompt := st.chat_input("Describe the QA query you need, e.g.: check for duplicate records"):
        if not api_key:
            st.error("Please enter API Key in sidebar")
            return

        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        render_message("user", prompt)

        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    client = Anthropic(api_key=api_key)
                    schema_text = format_selected_schema(all_schemas, st.session_state.selected_tables)
                    system_blocks = build_system_prompt(skill_prompt, reference, schema_text)

                    response = chat_with_claude(client, system_blocks, st.session_state.messages)

                    st.session_state.messages.append({"role": "assistant", "content": response})
                    st.rerun()  # Rerun to render with copy buttons

                except Exception as e:
                    st.error(f"Error: {str(e)}")


if __name__ == "__main__":
    main()
