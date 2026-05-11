# PostgreSQL MCP Server

An MCP server that exposes PostgreSQL database operations as tools for AI assistants.

## What is MCP?

Model Context Protocol (MCP) connects AI assistants to external tools and data. This server lets AI assistants execute SQL queries and inspect your PostgreSQL database schema.

## Setup

**Python version:** This project currently supports Python 3.10–3.13. Python 3.14 is excluded due to upstream dependency wheel support (e.g., `psycopg2-binary` and `pydantic-core`).

### 1. Install Dependencies

> **Note:** This project uses uv for dependency management. If you don't have uv installed, you can install it with:
> ```bash
> curl -LsSf https://astral.sh/uv/install.sh | sh
> ```
> See the [official uv documentation](https://docs.astral.sh/uv/getting-started/installation/) for alternative installation methods.

```bash
uv sync
```

### 2. Configure Database

Copy `.env.example` to `.env` and add your PostgreSQL credentials:

```bash
cp .env.example .env
```

Edit `.env`:
```
DB_NAME=your_database
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
```

## Testing

### MCP Inspector (Recommended)

> **Note:** The Inspector runs via `npx`, so you need Node.js (which includes npm). If you don't have it installed, get it from the official Node.js installer.

```bash
npx @modelcontextprotocol/inspector uv run python postgres-mcp-server/main.py
```

This opens a web UI where you can:
- View available tools under the **Tools** tab
- Test `get_schema`
- See real-time results

### Quick Test

```bash
uv run python postgres-mcp-server/main.py
```

Press `Ctrl+C` to stop. No errors = working correctly.

## Available Tools

**`get_schema()`** - Get database schema

## Connect to Cursor

Add to your Cursor MCP config (global settings):

```json
{
  "mcpServers": {
    "postgres": {
      "command": "uv",
      "args": ["run", "--project", "/absolute/path/to/postgres-mcp-server", "python", "postgres-mcp-server/main.py"]
    }
  }
}
```

Replace `/absolute/path/to/postgres-mcp-server` with your actual project path.

---

*Future Proof Data Science - Teaching data scientists to optimize workflows with AI*
