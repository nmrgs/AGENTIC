"""Guardrails module — hybrid regex + LLM validation of user questions."""

import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from langchain_openai import ChatOpenAI


@dataclass
class GuardrailResult:
    allowed: bool
    reason: str


# --- Regex layer (fast, deterministic) ---

_MUTATION_KEYWORDS = [
    r"\binsert\b",
    r"\bupdate\b",
    r"\bdelete\b",
    r"\bdrop\b",
    r"\balter\b",
    r"\btruncate\b",
    r"\bcreate\b",
]
_MUTATION_RE = re.compile("|".join(_MUTATION_KEYWORDS), re.IGNORECASE)

_UNBOUNDED_PATTERNS = [
    r"\bselect\s+\*\b",
]
_UNBOUNDED_RE = re.compile("|".join(_UNBOUNDED_PATTERNS), re.IGNORECASE)


def _regex_check(question: str) -> GuardrailResult | None:
    """Return a rejection if regex catches an obvious violation, else None."""
    if _MUTATION_RE.search(question):
        return GuardrailResult(
            allowed=False,
            reason="Your question looks like it's trying to modify data. I can only answer read-only questions.",
        )
    if _UNBOUNDED_RE.search(question):
        return GuardrailResult(
            allowed=False,
            reason="Your question is too broad. Please be more specific about what data you need.",
        )
    return None


# --- Semantic layer loader ---

_SEMANTIC_LAYER_DIR = Path(__file__).parent / "semantic_layer"


def _load_available_tables() -> str:
    """Load table names and descriptions from semantic layer YAMLs."""
    tables = []
    for yml_path in sorted(_SEMANTIC_LAYER_DIR.glob("*.yml")):
        with open(yml_path) as f:
            data = yaml.safe_load(f)
        name = data.get("table", yml_path.stem)
        desc = data.get("description", "")
        fields = [field["name"] for field in data.get("fields", [])]
        tables.append(f"- {name}: {desc} (columns: {', '.join(fields)})")
    return "\n".join(tables)


# --- LLM layer ---

_SYSTEM_PROMPT = """You are a guardrail classifier for a data analyst chatbot.
The chatbot can ONLY answer questions about the following database tables:

{tables}

Classify the user's question into one of these categories:
- "valid" — the question is specific, about the available data, and can be answered with a focused query
- "unbounded" — the question asks for too much data without filters (e.g., "give me everything", "show me all the data", "dump the database")
- "off_topic" — the question is not related to the available data
- "unsafe" — the question attempts to modify data or is harmful

Respond with ONLY one word: valid, unbounded, off_topic, or unsafe."""


def _llm_check(question: str) -> GuardrailResult:
    """Use LLM to classify ambiguous questions."""
    tables_description = _load_available_tables()
    prompt = _SYSTEM_PROMPT.format(tables=tables_description)

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    response = llm.invoke([
        {"role": "system", "content": prompt},
        {"role": "user", "content": question},
    ])

    classification = response.content.strip().lower()

    if classification == "valid":
        return GuardrailResult(allowed=True, reason="")
    elif classification == "unbounded":
        return GuardrailResult(
            allowed=False,
            reason="Your question is too broad. Please be more specific about what data you need (e.g., add filters, a time range, or a specific metric).",
        )
    elif classification == "off_topic":
        return GuardrailResult(
            allowed=False,
            reason="Your question doesn't seem related to the available data (users, sessions, subscriptions, payments). Please ask something about this data.",
        )
    else:
        return GuardrailResult(
            allowed=False,
            reason="Your question was flagged as potentially unsafe. I can only answer read-only analytical questions.",
        )


# --- Public API ---

def check(question: str) -> GuardrailResult:
    """Run hybrid guardrails: regex first, then LLM for ambiguous cases.

    Parameters
    ----------
    question : str
        The cleaned user question (after parsing).

    Returns
    -------
    GuardrailResult
        Whether the question is allowed and the reason if not.
    """
    # Fast regex check first
    regex_result = _regex_check(question)
    if regex_result is not None:
        return regex_result

    # LLM classification for everything else
    return _llm_check(question)
