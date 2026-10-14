import argparse
import json
from pathlib import Path
from typing import Any

from shared.runtime import load_app


def normalize(value: Any) -> Any:
    if isinstance(value, list):
        return [normalize(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {key: normalize(item) for key, item in value.items()}
    if "anyOf" in result:
        choices = result["anyOf"]
        nonnull = [item for item in choices if item.get("type") != "null"]
        if len(nonnull) == 1 and len(nonnull) < len(choices):
            result.pop("anyOf")
            result.update(nonnull[0])
            result["nullable"] = True
    if "const" in result:
        result["enum"] = [result.pop("const")]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the live FastAPI contract as APIM OpenAPI 3.0.3")
    parser.add_argument("--output", default="infra/terraform/gateway/catalog.openapi.json")
    args = parser.parse_args()
    module = load_app("src/catalog-api/app/main.py", "export_catalog")
    contract = normalize(module.api.openapi())
    contract["openapi"] = "3.0.3"
    Path(args.output).write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()