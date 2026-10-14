import pytest
from mcp.server.fastmcp.exceptions import ToolError

from shared.runtime import load_app


@pytest.mark.parametrize("service,expected", [
    ("mcp-catalog", {"search_services", "get_service", "list_versions", "get_service_contract"}),
    ("mcp-operations", {"evaluate_access_request", "create_access_request"}),
])
async def test_real_sdk_tool_schemas(service, expected):
    module = load_app(f"src/{service}/app/main.py", service.replace("-", "_"))
    tools = await module.mcp.list_tools()
    assert {tool.name for tool in tools} == expected
    assert all(tool.inputSchema["type"] == "object" for tool in tools)
    tool = "get_service" if service == "mcp-catalog" else "create_access_request"
    with pytest.raises(ToolError):
        await module.mcp.call_tool(tool, {"service_id": "../invalid"})