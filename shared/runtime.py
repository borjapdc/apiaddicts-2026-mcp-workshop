import asyncio
import hmac
import os
from typing import Any

import httpx
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class OriginAuth:
    def __init__(self, app: ASGIApp, role: str = "reader") -> None:
        self.app = app
        self.role = role
        self.required = os.getenv("REQUIRE_AUTH", "0") == "1"
        if self.required and not os.getenv("BACKEND_READ_TOKEN"):
            raise RuntimeError("Cloud origin credential is required")
        if self.required and self.role != "reader" and not os.getenv("BACKEND_WRITE_TOKEN"):
            raise RuntimeError("Cloud write credential is required")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"] != "/health" and self.required:
            headers = dict(scope.get("headers", []))
            supplied = headers.get(b"x-backend-token", b"").decode("utf-8", errors="replace")
            write = self.role == "operator" or scope["path"] == "/api/access-requests"
            expected = os.environ["BACKEND_WRITE_TOKEN" if write else "BACKEND_READ_TOKEN"]
            if not hmac.compare_digest(supplied, expected):
                await JSONResponse({"detail": "Origin authentication required"}, status_code=401)(
                    scope, receive, send
                )
                return
        await self.app(scope, receive, send)


async def catalog_request(method: str, path: str, **kwargs: Any) -> Any:
    base = os.environ.get("CATALOG_API_URL", "http://localhost:8001").rstrip("/")
    token = os.getenv("BACKEND_WRITE_TOKEN" if method == "POST" else "BACKEND_READ_TOKEN", "")
    for attempt in range(3 if method == "GET" else 1):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.request(
                    method, base + path, headers={"x-backend-token": token}, **kwargs
                )
            if response.status_code == 404:
                raise ValueError("Service not found")
            if response.status_code >= 500 and method == "GET" and attempt < 2:
                await asyncio.sleep(0.1 * 2**attempt)
                continue
            response.raise_for_status()
            return response.json()
        except (httpx.TimeoutException, httpx.NetworkError) as error:
            if method != "GET" or attempt == 2:
                raise RuntimeError("Catalog unavailable or timed out") from error
            await asyncio.sleep(0.1 * 2**attempt)
        except httpx.HTTPStatusError as error:
            raise RuntimeError("Catalog rejected the request") from error
    raise RuntimeError("Catalog unavailable")


def load_app(path: str, name: str) -> Any:
    import importlib.util
    import sys
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(name, Path(path))
    if spec is None or spec.loader is None:
        raise RuntimeError("Application module not found")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def mcp_app(server: Any, role: str) -> ASGIApp:
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    async def health(request: Any) -> JSONResponse:
        try:
            await catalog_request("GET", "/health")
            return JSONResponse({"status": "healthy", "service": server.name})
        except RuntimeError:
            return JSONResponse({"status": "unhealthy"}, status_code=503)

    application = server.streamable_http_app()
    application.routes.append(Route("/health", health))
    return OriginAuth(application, role)


def server_settings() -> dict[str, Any]:
    from mcp.server.transport_security import TransportSecuritySettings

    hosts = ["localhost:*", "127.0.0.1:*", "[::1]:*", "mcp-catalog:*", "mcp-operations:*"]
    hosts.extend(filter(None, os.getenv("MCP_ALLOWED_HOSTS", "").split(",")))
    hosts.extend([host[:-2] for host in hosts if host.endswith(":*")])
    return {
        "stateless_http": True,
        "json_response": True,
        "transport_security": TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=hosts,
            allowed_origins=["http://localhost:*", "http://127.0.0.1:*"],
        ),
    }