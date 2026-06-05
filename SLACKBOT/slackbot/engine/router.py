"""Router module — LLM-based table selector for user questions."""

from pathlib import Path

import yaml
from langchain_openai import ChatOpenAI


_SEMANTIC_LAYER_DIR = Path(__file__).parents[1] / "intake" / "semantic_layer"

_SYSTEM_PROMPT = """You are a data routing assistant. Given a user's natural language question about data, determine which database tables are needed to answer it.

Available tables:

{tables}

Rules:
- Return ONLY a comma-separated list of table names (e.g., "users, payments")
- Include a table only if its columns are needed to answer the question
- Include tables needed for joins (e.g., if the question asks about revenue per country, you need both "payments" and "users" via "subscriptions")
- If unsure, include all tables that might be relevant rather than missing one"""


def _load_table_descriptions() -> str:
    """Load table names, descriptions, columns, and relationships from semantic layer YAMLs."""
    tables = []
    for yml_path in sorted(_SEMANTIC_LAYER_DIR.glob("*.yml")):
        with open(yml_path) as f:
            data = yaml.safe_load(f)
        name = data.get("table", yml_path.stem)
        desc = data.get("description", "")
        fields = [f"{f['name']} ({f['description']})" for f in data.get("fields", [])]
        relationships = data.get("relationships", [])
        rel_desc = ""
        if relationships:
            rels = [f"{r['field']} -> {r['references']['table']}.{r['references']['field']}" for r in relationships]
            rel_desc = f"\n    Joins: {', '.join(rels)}"
        tables.append(f"- {name}: {desc}\n    Columns: {', '.join(fields)}{rel_desc}")
    return "\n".join(tables)


_AVAILABLE_TABLES = {"users", "payments", "sessions", "subscriptions"}


def route(question: str) -> list[str]:
    """Determine which tables are relevant to answer the user's question.

    Parameters
    ----------
    question : str
        The cleaned user question.

    Returns
    -------
    list[str]
        List of table names needed to answer the question.
    """
    tables_description = _load_table_descriptions()
    prompt = _SYSTEM_PROMPT.format(tables=tables_description)

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    response = llm.invoke([
        {"role": "system", "content": prompt},
        {"role": "user", "content": question},
    ])

    raw = response.content.strip()
    selected = [t.strip().lower() for t in raw.split(",")]
    # Filter to only valid table names
    selected = [t for t in selected if t in _AVAILABLE_TABLES]

    # Fallback: if nothing matched, use all tables
    if not selected:
        selected = list(_AVAILABLE_TABLES)

    return selected
