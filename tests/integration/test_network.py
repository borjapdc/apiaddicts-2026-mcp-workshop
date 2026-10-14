import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

from shared.runtime import load_app

client_module = load_app("src/mcp-client/client.py", "network_client")


@pytest.fixture(scope="module")
def endpoints(tmp_path_factory):
    directory = tmp_path_factory.mktemp("network")
    processes = []
    streams = []
    urls = {}
    try:
        for service in ["catalog-api", "mcp-catalog", "mcp-operations"]:
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
            urls[service] = f"http://127.0.0.1:{port}"
            env = {**os.environ, "PYTHONPATH": str(Path.cwd()), "REQUIRE_AUTH": "1",
                   "BACKEND_READ_TOKEN": "synthetic-read", "BACKEND_WRITE_TOKEN": "synthetic-write",
                   "CATALOG_DB": str(directory / "requests.db"), "CATALOG_API_URL": urls["catalog-api"]}
            stream = (directory / f"{service}.log").open("w")
            streams.append(stream)
            processes.append(subprocess.Popen([
                sys.executable, "-m", "uvicorn", "app.main:app", "--app-dir", f"src/{service}",
                "--port", str(port), "--no-access-log",
            ], env=env, stdout=stream, stderr=stream))
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                try:
                    if httpx.get(urls[service] + "/health", timeout=1).status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(0.1)
            else:
                pytest.fail(f"Readiness failed for {service}; see {directory}")
        yield urls
    finally:
        for process in processes:
            process.terminate()
        for process in processes:
            process.wait(timeout=10)
        for stream in streams:
            stream.close()


async def test_native_protocol_and_mutation(endpoints):
    reader = {"x-backend-token": "synthetic-read"}
    operator = {"x-backend-token": "synthetic-write"}
    catalog = endpoints["mcp-catalog"] + "/mcp"
    operations = endpoints["mcp-operations"] + "/mcp"
    listed = await client_module.invoke(catalog, headers=reader)
    assert listed["initialize"]["protocolVersion"] >= "2025-06-18"
    assert len(listed["result"]["tools"]) == 4
    search = await client_module.invoke(catalog, "search_services", {"query": "payments"}, reader)
    assert search["result"]["structuredContent"]["services"][0]["id"] == "payments"
    contract = await client_module.invoke(catalog, "get_service_contract", {"service_id": "orders"}, reader)
    assert contract["result"]["structuredContent"]["contract"]["openapi"] == "3.0.3"
    listed_operations = await client_module.invoke(operations, headers=operator)
    assert len(listed_operations["result"]["tools"]) == 2
    arguments = {"service_id": "payments", "consumer_id": "demo-client", "purpose": "Synthetic workshop demo"}
    evaluated = await client_module.invoke(operations, "evaluate_access_request", arguments, operator)
    assert evaluated["result"]["structuredContent"]["approved"] is False
    created = await client_module.invoke(operations, "create_access_request", arguments, operator)
    assert created["result"]["structuredContent"]["status"] == "demo-pending"
    repeated = await client_module.invoke(operations, "create_access_request", arguments, operator)
    assert repeated["result"]["structuredContent"]["request_id"] == created["result"]["structuredContent"]["request_id"]


async def test_protocol_errors_and_no_bypass(endpoints):
    async with httpx.AsyncClient() as transport:
        for service in ["mcp-catalog", "mcp-operations"]:
            assert (await transport.post(endpoints[service] + "/mcp", json={})).status_code == 401
        assert (await transport.post(endpoints["mcp-operations"] + "/mcp", json={},
                headers={"x-backend-token": "synthetic-read"})).status_code == 401
    result = await client_module.invoke(endpoints["mcp-catalog"] + "/mcp", "get_service",
                                        {"service_id": "unknown"}, {"x-backend-token": "synthetic-read"})
    assert result["result"]["isError"]
    invalid = await client_module.invoke(endpoints["mcp-operations"] + "/mcp", "create_access_request",
                                         {"service_id": "../invalid"}, {"x-backend-token": "synthetic-write"})
    assert invalid["result"]["isError"]