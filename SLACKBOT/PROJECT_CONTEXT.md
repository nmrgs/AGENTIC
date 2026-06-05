# PROJECT_CONTEXT.md

## Project Overview

**Talk to Your Data** is a Slack-based AI agent that allows technical and non-technical users to ask natural language questions against a PostgreSQL database. Users interact through Slack; the agent interprets the question, queries the database, and returns a plain English summary with optional tables or charts — all within the Slack conversation.

## System Scope

### In Scope

- Receiving natural language questions from Slack
- Validating questions against guardrails (relevance, safety, volume)
- Reformulating business questions into data queries
- Routing questions to the correct semantic model (tables, relationships, columns)
- Generating and executing read-only queries against PostgreSQL
- Formatting results as summaries, tables, or charts
- Posting answers back to Slack

### Out of Scope

- Write operations on the database (insert, update, delete)
- Questions unrelated to available data
- Unbounded queries that pull excessive rows

## Architecture Summary

The system is composed of three subsystems plus external dependencies:

### Intake

Receives the user question from Slack and prepares it for processing.

- **Parser** — reformulates the raw business question into a structured data question.
- **Guardrails** — validates that the question is safe to process: it must concern available data, must not request too many rows, and must not attempt data modification.

### Engine

The core reasoning layer that selects the right data context and generates a query.

- **Router / Data Selector** — matches the parsed question to the appropriate semantic model (table definitions, relationships, column descriptions).
- **PandasAI Multi-Agent** — receives the reformulated question plus semantic model context, generates code, queries PostgreSQL, and returns a raw result.

### Output

- **Output Formatter** — transforms the raw query result into a plain English summary accompanied by a table or chart, then posts the answer back to Slack.

### External Environments

- **PostgreSQL Database** — the source of truth being queried.
- **Semantic Model** — metadata layer describing tables, columns, and relationships used for routing and context injection.

## Key Inputs and Outputs

| Direction | Description |
|-----------|-------------|
| **Input** | A natural language question sent by a user in Slack |
| **Output** | A plain English summary + table or chart posted back to the same Slack channel |

## Design Rationale

- **Guardrails-first approach** — questions are validated before any query generation, preventing unsafe or unbounded operations from reaching the database.
- **Semantic model routing** — instead of exposing the full schema to the LLM, questions are matched to a focused subset of metadata, improving accuracy and reducing hallucination.
- **Separation of intake, engine, and output** — keeps parsing/validation, reasoning/querying, and formatting as independent concerns, making each subsystem testable and replaceable.
- **Slack as the interface** — meets users where they already work, removing the need for a dedicated UI and lowering adoption friction.
- **Read-only by design** — the system only generates SELECT queries, eliminating risk of accidental data mutation.
