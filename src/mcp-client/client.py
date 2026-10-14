import argparse
import asyncio
import json
import os
import sys
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.shared.exceptions import McpError
from mcp.types import Implementation


async def invoke(url: str, tool: str | None = None, arguments: dict[str, Any] | None = None,
                 headers: dict[str, str] | None = None) -> dict[str, Any]:
    async with (
        streamablehttp_client(url, headers=headers or {}, timeout=15) as (read, write, _),
        ClientSession(read, write, client_info=Implementation(
            name="apiaddicts-cli", version="1.0.0"
        )) as session,
    ):
        initialized = await session.initialize()
        result = await session.call_tool(tool, arguments or {}) if tool else await session.list_tools()
        return {"initialize": initialized.model_dump(mode="json", by_alias=True),
                "result": result.model_dump(mode="json", by_alias=True)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Official SDK MCP initialize/list/call client")
    parser.add_argument("--url", required=True)
    parser.add_argument("--tool")
    parser.add_argument("--arguments", default="{}", help="JSON object")
    parser.add_argument("--key-env", default="APIM_READER_KEY", help="Environment variable, not a literal key")
    parser.add_argument("--backend-token-env", help="Origin credential environment variable")
    args = parser.parse_args()
    headers = {}
    if os.getenv(args.key_env):
        headers["Ocp-Apim-Subscription-Key"] = os.environ[args.key_env]
    if args.backend_token_env and os.getenv(args.backend_token_env):
        headers["x-backend-token"] = os.environ[args.backend_token_env]
    try:
        result = asyncio.run(invoke(args.url, args.tool, json.loads(args.arguments), headers))
        print(json.dumps(result, indent=2, ensure_ascii=True))
        if result["result"].get("isError"):
            sys.exit(1)
    except (ExceptionGroup, httpx.HTTPError, ValueError, RuntimeError, McpError):
        print(json.dumps({"status": "FAIL", "error": "MCP request failed; check auth, health and URL"}))
        sys.exit(1)


if __name__ == "__main__":
    main()