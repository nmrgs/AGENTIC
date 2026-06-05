"""Auto-create PandasAI datasets from semantic layer YAMLs if they don't exist."""

import os
from pathlib import Path

import yaml
import pandasai as pai


_SEMANTIC_LAYER_DIR = Path(__file__).parents[1] / "intake" / "semantic_layer"
_DATASETS_DIR = Path.cwd() / "datasets"

# Map semantic layer data_type to PandasAI column type
_TYPE_MAP = {
    "integer": "integer",
    "numeric": "float",
    "timestamp without time zone": "datetime",
    "character varying": "string",
}


def _build_schema(table_data: dict) -> dict:
    """Build a PandasAI schema dict from a semantic layer YAML."""
    table_name = table_data["table"]

    columns = []
    for field in table_data.get("fields", []):
        col_type = _TYPE_MAP.get(field.get("data_type", "string"), "string")
        columns.append({
            "name": field["name"],
            "type": col_type,
            "description": field.get("description", ""),
        })

    schema = {
        "name": table_name,
        "source": {
            "type": "postgres",
            "connection": {
                "host": os.environ["DB_HOST"].strip(),
                "port": int(os.environ.get("DB_PORT", "5432").strip()),
                "user": os.environ["DB_USER"].strip(),
                "password": os.environ["DB_PASS"].strip(),
                "database": os.environ["DB_NAME"].strip(),
            },
            "table": table_name,
            "columns": columns,
        },
        "description": table_data.get("description", ""),
    }

    # Add optional enrichments
    if table_data.get("primary_key"):
        schema["primary_key"] = table_data["primary_key"]

    if table_data.get("relationships"):
        schema["relationships"] = table_data["relationships"]

    if table_data.get("measures"):
        schema["measures"] = table_data["measures"]

    if table_data.get("golden_queries"):
        schema["golden_queries"] = table_data["golden_queries"]

    return schema


def ensure_datasets():
    """Create PandasAI datasets if they don't already exist.

    Reads semantic layer YAMLs and writes schema.yaml files into
    datasets/public/<table_name>/ for each table.
    """
    # Check if datasets already exist
    if (_DATASETS_DIR / "public").exists():
        return

    print("First run: creating PandasAI datasets from semantic layer...")

    for yml_path in sorted(_SEMANTIC_LAYER_DIR.glob("*.yml")):
        with open(yml_path) as f:
            table_data = yaml.safe_load(f)

        table_name = table_data["table"]
        schema = _build_schema(table_data)

        # Write schema.yaml
        dataset_dir = _DATASETS_DIR / "public" / table_name
        dataset_dir.mkdir(parents=True, exist_ok=True)

        schema_path = dataset_dir / "schema.yaml"
        with open(schema_path, "w") as f:
            yaml.dump(schema, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

        print(f"  Created dataset: public/{table_name}")

    print("Datasets ready.")
