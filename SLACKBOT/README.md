# slackbot

A Slack-based AI agent that answers natural language questions against a PostgreSQL database.

## Architecture

```
                         ┌─────────────────────────────────────────────────────┐
                         │                   Slackbot                          │
                         │                                                     │
   ┌──────────┐         │  ┌─────────────┐   ┌─────────────┐   ┌──────────┐  │
   │          │  Slack   │  │   INTAKE    │   │   ENGINE    │   │  OUTPUT  │  │
   │   User   │────────► │  │             │   │             │   │          │  │
   │          │◄──────── │  │  parser     │──►│  router     │──►│formatter │  │
   └──────────┘         │  │  guardrails  │   │  pandasai   │   │(LLM sum) │  │
                         │  └─────────────┘   └──────┬──────┘   └──────────┘  │
                         │                           │                         │
                         └───────────────────────────┼─────────────────────────┘
                                                     │
                                          ┌──────────▼──────────┐
                                          │  External Services   │
                                          │                      │
                                          │  PostgreSQL    LLM   │
                                          │  Semantic Layer       │
                                          └──────────────────────┘
```

## Setup

```bash
uv sync
```

Copy `.env.example` to `.env` and fill in your values:
- `SLACK_BOT_TOKEN` / `SLACK_APP_TOKEN` — from your Slack app config
- `OPENAI_API_KEY` — for LLM calls
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASS` — PostgreSQL credentials

## Run

```bash
uv run slackbot
```

On first run, PandasAI datasets are auto-created from the semantic layer definitions and your `.env` credentials.

---

## Intake

The intake subsystem receives raw user messages from Slack and validates them before processing.

**Parser** (`slackbot/intake/parser.py`)
- Strips the `<@BOT_ID>` mention from the message
- Normalizes whitespace

**Guardrails** (`slackbot/intake/guardrails.py`)

Hybrid validation — regex first, LLM for ambiguous cases:

- *Regex*: rejects SQL mutation keywords (`INSERT`, `UPDATE`, `DELETE`, `DROP`, etc.) and raw `SELECT *`
- *LLM*: classifies questions as `valid`, `unbounded`, `off_topic`, or `unsafe` using table/column context from the semantic layer

**Flow:**
```
Raw Slack message → Parser → Guardrails → IntakeResult(question, allowed, rejection_reason)
```

---

## Engine

The engine subsystem takes a validated question and returns an answer by querying PostgreSQL via PandasAI.

**Router** (`slackbot/engine/router.py`)
- LLM-based table selector — determines which tables are relevant to the question
- Uses `gpt-4o-mini` with table descriptions, columns, and relationships as context

**Agent** (`slackbot/engine/agent.py`)
- Loads selected datasets with `pai.load()`
- Creates a PandasAI `Agent` with `gpt-4.1-mini` via LiteLLM
- Calls `agent.chat(question)` and returns the raw response

**Dataset Setup** (`slackbot/engine/setup_datasets.py`)
- Auto-creates `datasets/public/<table>/schema.yaml` on first run
- Reads semantic layer YAMLs + `.env` credentials
- Includes columns, relationships, measures, and golden queries

**Flow:**
```
Validated question → Router (pick tables) → PandasAI Agent (query DB) → EngineResult(raw_response, tables_used)
```

---

## Output

The output subsystem formats raw PandasAI responses into Slack-friendly messages.

**Formatter** (`slackbot/output/formatter.py`)
- Detects response type: number, DataFrame, chart, or plain text
- **Numbers**: formatted as bold text
- **DataFrames**: rendered as monospace code blocks
- **Charts**: saved to temp file, uploaded to Slack as an image
- Generates a plain English summary using `gpt-4o-mini`

**Flow:**
```
EngineResult → Detect type → Format data → LLM summary → FormattedOutput(summary, text_data, chart_path)
```
