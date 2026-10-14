from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from shared.runtime import catalog_request, mcp_app, server_settings

mcp = FastMCP("mcp-operations", **server_settings())
ServiceId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]{1,39}$")]
ConsumerId = Annotated[str, Field(pattern=r"^demo-[a-z0-9-]{1,40}$")]
Purpose = Annotated[str, Field(min_length=10, max_length=240, pattern=r"^[^\x00-\x1f]+$")]


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, idempotentHint=True))
async def evaluate_access_request(service_id: ServiceId, consumer_id: ConsumerId,
                                  purpose: Purpose) -> dict[str, Any]:
    """Evaluate a fictional request; this never grants real authorization or approval."""
    service = await catalog_request("GET", f"/api/services/{service_id}")
    return {
        "service_id": service_id, "consumer_id": consumer_id,
        "decision": "manual-review" if service["classification"] == "restricted" else "demo-eligible",
        "approved": False, "notice": "Fictitious evaluation; not approval or real authorization",
    }


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True))
async def create_access_request(service_id: ServiceId, consumer_id: ConsumerId,
                                purpose: Purpose) -> dict[str, Any]:
    """Record a deterministic fictional request, only on the operator-authorized server."""
    return await catalog_request("POST", "/api/access-requests", json={
        "service_id": service_id, "consumer_id": consumer_id, "purpose": purpose,
    })


app = mcp_app(mcp, "operator")