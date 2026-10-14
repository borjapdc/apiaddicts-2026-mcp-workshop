import argparse
import asyncio
import hashlib
import json
import os
import statistics
import time
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from scripts.lib import presentation
from scripts.lib.workshop import (
    LOCAL,
    ROOT,
    Blocked,
    assert_subscription,
    az,
    keys,
    output,
    record,
    run,
    write_json,
)
from shared.runtime import load_app


def configuration() -> dict[str, Any]:
    path = LOCAL / "workshop.json"
    if not path.exists():
        raise Blocked("Cloud outputs missing; run deploy --apply, or use demo --step discover")
    return json.loads(path.read_text())


def cli(url: str, tool: str | None = None, arguments: dict[str, Any] | None = None,
        role: str = "reader", credential: str | None = None) -> None:
    variable = f"APIM_{role.upper()}_KEY"
    previous = os.environ.get(variable)
    try:
        if credential:
            os.environ[variable] = credential
        command = ["uv", "run", "python", "src/mcp-client/client.py", "--url", url, "--key-env", variable]
        if tool:
            command += ["--tool", tool, "--arguments", json.dumps(arguments or {})]
        label = f"MCP | {tool or 'initialize + tools/list'} | {role}"
        with presentation.phase(label):
            execution = run(*command, capture=True, check=False)
            if execution.returncode:
                raise Blocked("MCP request failed; check auth, health and endpoint; no secrets logged")
            try:
                payload = json.loads(execution.stdout)
            except ValueError as error:
                raise Blocked("Client output was not valid JSON; protocol result cannot be displayed") from error
            endpoint_id = hashlib.sha256(url.encode()).hexdigest()[:12]
            artifact = LOCAL / "demo-results" / f"{endpoint_id}-{tool or 'tools-list'}.json"
            write_json(artifact, presentation.safe(payload), private=True)
            presentation.mcp_result(payload, tool)
    finally:
        if previous is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = previous


async def load(workshop: dict[str, Any]) -> None:
    with presentation.phase("Obtener credencial de lectura en memoria"):
        credentials = keys(workshop)
    url = workshop["gateway_endpoints"]["mcp-catalog"]
    codes: list[int] = []
    attempt_codes: list[int] = []
    durations: list[float] = []
    burst_budget = min(workshop.get("rate_limit_calls", 5) + 6, 25)

    async def observe_response(response: httpx.Response) -> None:
        codes.append(response.status_code)
        attempt_codes.append(response.status_code)

    def factory(headers: dict[str, str] | None = None, timeout: httpx.Timeout | None = None,
                auth: httpx.Auth | None = None) -> httpx.AsyncClient:
        return httpx.AsyncClient(headers=headers, timeout=timeout, auth=auth, follow_redirects=True,
                                 event_hooks={"response": [observe_response]})

    await presentation.wait_window(workshop.get("rate_limit_period_seconds", 30) + 1, "Preparar carga APIM")
    for _ in range(12):
        started = time.perf_counter()
        attempt_codes.clear()
        try:
            with presentation.expected_rate_limits(), presentation.phase(
                "Intento de carga MCP", expected_rate_limit=True, observed_codes=attempt_codes
            ):
                async with (
                    streamablehttp_client(url, headers={"Ocp-Apim-Subscription-Key": credentials["reader"]},
                                          timeout=15, httpx_client_factory=factory) as (read, write, _),
                    ClientSession(read, write) as session,
                ):
                    await session.initialize()
                    result = await session.call_tool("get_service", {"service_id": "payments"})
                    if not result.isError:
                        durations.append((time.perf_counter() - started) * 1000)
                        if not presentation.detailed():
                            presentation.status("get_service", "PASS", f"{durations[-1]:.0f}ms")
        except (ExceptionGroup, httpx.HTTPError) as error:
            if 429 not in attempt_codes or not presentation.is_expected_rate_limit(error, attempt_codes):
                raise Blocked("Unexpected MCP load failure; inspect auth and connectivity") from error
            if not presentation.detailed():
                presentation.status("Rate limit", "WARN", "HTTP 429 observado; bloqueo esperado")
        if len(codes) >= burst_budget:
            break
    if 429 not in codes:
        raise Blocked("No 429 observed in bounded MCP requests")
    await presentation.wait_window(workshop.get("rate_limit_period_seconds", 30) + 1, "Recuperar ventana APIM")
    module = load_app(str(ROOT / "src/mcp-client/client.py"), "recovery_client")
    started = time.perf_counter()
    recovered = await module.invoke(url, "get_service", {"service_id": "payments"},
                                    {"Ocp-Apim-Subscription-Key": credentials["reader"]})
    if recovered["result"]["isError"]:
        raise Blocked("Post-window valid tool call did not recover")
    durations.append((time.perf_counter() - started) * 1000)
    quantiles = statistics.quantiles(durations, n=100, method="inclusive") if len(durations) >= 2 else None
    record("GOV-LOAD", "PASS", "scripts/demo/demo.sh --step govern", {
        "burst_http_responses": len(codes), "http_budget_including_recovery": 30,
        "http_codes": codes, "concurrency": 1, "successful_samples": len(durations),
        "p50_ms": statistics.median(durations) if durations else None,
        "p95_ms": quantiles[94] if quantiles else (durations[0] if durations else None),
        "measurement": "End-to-end initialize plus tools/call; deliberately small sample, not a TPS benchmark",
        "indicative_threshold_ms": 1500, "rate_limit_observed": 429, "recovery": "tools/call succeeded after window"})


def observe(workshop: dict[str, Any]) -> None:
    workspace = workshop["foundation"]["log_workspace_guid"]
    query = (ROOT / "docs/queries/workspace.kql").read_text()
    with presentation.phase("Consultar trazas MCP reales con KQL"):
        result = az("monitor", "log-analytics", "query", "--workspace", workspace, "--analytics-query", query)
    write_json(LOCAL / "observability.json", result)
    if not result or not any(item.get("tool") for item in result):
        record("OBS", "BLOCKED", "scripts/demo/observe.sh", {"reason": "No real gen_ai.tool.name rows observed; ingestion may be delayed", "workspace": workspace})
        raise Blocked("No real MCP tool telemetry yet; rerun observe after ingestion")
    record("OBS", "PASS", "scripts/demo/observe.sh", {"workspace": workspace, "rows": result})


def configure_mcp(workshop: dict[str, Any] | None) -> None:
    endpoints = workshop["gateway_endpoints"] if workshop else {
        "mcp-catalog": "http://localhost:8002/mcp", "mcp-operations": "http://localhost:8003/mcp"}
    servers = {}
    for name, url in endpoints.items():
        server: dict[str, Any] = {"type": "http", "url": url}
        if workshop:
            role = "operator" if name == "mcp-operations" else "reader"
            server["headers"] = {"Ocp-Apim-Subscription-Key": "${input:" + role + "Key}"}
        servers[name] = server
    inputs = [{"id": role + "Key", "type": "promptString", "description": f"Workshop {role} product key", "password": True}
              for role in ["reader", "operator"]] if workshop else []
    write_json(ROOT / ".vscode/mcp.json", {"servers": servers, "inputs": inputs}, private=True)
    print("PASS    Generated ignored .vscode/mcp.json; secrets are prompt inputs, never embedded")


def execute(args: argparse.Namespace) -> None:
    if args.command == "configure-mcp":
        if (ROOT / "infra/terraform/gateway/terraform.tfstate").exists():
            target = assert_subscription()
            workshop = {"target": target, "foundation": output("foundation")["foundation"],
                        "backends": output("workload")["backends"], **output("gateway")}
            if not workshop.get("gateway_endpoints"):
                raise Blocked("Gateway outputs not yet available; no cloud URL guessed")
            write_json(LOCAL / "workshop.json", workshop)
        configure_mcp(configuration() if (LOCAL / "workshop.json").exists() else None)
        return
    if args.command == "demo" and args.step == "discover":
        cli("http://localhost:8002/mcp")
        cli("http://localhost:8002/mcp", "search_services", {"query": "payments"})
        cli("http://localhost:8002/mcp", "get_service_contract", {"service_id": "orders"})
        cli("http://localhost:8003/mcp", role="operator")
        if presentation.detailed():
            print("OpenAPI: http://localhost:8001/openapi.json; dashboard: http://localhost:15888")
        else:
            presentation.table("Pantallas de la demo", ["Vista", "URL"], [
                ["Aspire Dashboard", "http://localhost:15888"],
                ["OpenAPI", "http://localhost:8001/docs"],
            ])
            presentation.status("Evidencia", "INFO", ".local/demo-results/*.json")
        return
    if args.command == "demo" and args.step == "foundry":
        if presentation.detailed():
            print((ROOT / "docs/FOUNDRY_OPTIONAL.md").read_text())
        else:
            presentation.table("Foundry opcional | solo documentacion", ["Aspecto", "Alcance"], [
                ["Estado", "Preview; NO desplegado, no hay modelos comerciales"],
                ["APIM", "Requiere v2 elegible, mismo tenant y suscripcion"],
                ["Developer", "El gateway de esta demo no es elegible para asociacion Foundry"],
                ["Gobierno", "Tokens LLM y llamadas MCP son limites diferentes"],
                ["Guia", "docs/FOUNDRY_OPTIONAL.md"],
            ])
        return
    with presentation.phase("Verificar suscripcion MVP"):
        assert_subscription()
    workshop = configuration()
    if args.command == "observe":
        observe(workshop)
    elif args.command == "load" or args.step == "govern":
        asyncio.run(load(workshop))
        observe(workshop)
    elif args.step == "cloud":
        with presentation.phase("Obtener credenciales de producto en memoria"):
            credentials = keys(workshop)
        for name, url in workshop["gateway_endpoints"].items():
            role = "operator" if name == "mcp-operations" else "reader"
            cli(url, role=role, credential=credentials[role])
        if presentation.detailed():
            print(json.dumps({"endpoints": workshop["gateway_endpoints"], "resource_group": workshop["foundation"]["resource_group_name"]}, indent=2))
        else:
            presentation.table("Endpoints APIM", ["Servidor", "Endpoint"], [
                [name, url] for name, url in workshop["gateway_endpoints"].items()
            ])
            presentation.status("Evidencia", "INFO", ".local/demo-results/*.json; sin claves")