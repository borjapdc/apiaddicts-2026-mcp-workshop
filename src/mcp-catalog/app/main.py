from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from shared.runtime import catalog_request, mcp_app, server_settings

mcp = FastMCP("mcp-catalog", **server_settings())
read_only = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True)
ServiceId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]{1,39}$")]


@mcp.tool(annotations=read_only)
async def search_services(
    query: Annotated[str, Field(max_length=120)],
    category: Annotated[str | None, Field(max_length=40)] = None,
    limit: Annotated[int, Field(ge=1, le=20)] = 10,
) -> dict[str, Any]:
    """Search the synthetic corporate catalog, optionally filtered by category."""
    params: dict[str, Any] = {"query": query, "limit": limit}
    if category is not None:
        params["category"] = category
    return {"services": await catalog_request("GET", "/api/services", params=params)}


@mcp.tool(annotations=read_only)
async def get_service(service_id: ServiceId) -> dict[str, Any]:
    """Read a service's classification, fictional owner and explicitly fictitious SLA."""
    return await catalog_request("GET", f"/api/services/{service_id}")


@mcp.tool(annotations=read_only)
async def list_versions(service_id: ServiceId) -> dict[str, Any]:
    """List deterministic demo versions of an existing service."""
    return await catalog_request("GET", f"/api/services/{service_id}/versions")


@mcp.tool(annotations=read_only)
async def get_service_contract(service_id: ServiceId) -> dict[str, Any]:
    """Read an illustrative OpenAPI contract; its business path is not a live endpoint."""
    return await catalog_request("GET", f"/api/services/{service_id}/contract")


app = mcp_app(mcp, "reader")