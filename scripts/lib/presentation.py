import asyncio
import json
import logging
import time
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import anyio
import httpx
from rich import box
from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn, TimeRemainingColumn
from rich.table import Table
from rich.text import Text

console = Console(highlight=False, markup=False)
_detailed = False
STYLES = {"PASS": "green", "FAIL": "red", "BLOCKED": "yellow", "WARN": "yellow", "INFO": "cyan"}
SENSITIVE = {"authorization", "ocp-apim-subscription-key", "x-backend-token", "primarykey",
             "secondarykey", "password", "backend_read_token", "backend_write_token"}


def configure(detailed: bool = False) -> None:
    global _detailed
    _detailed = detailed


def detailed() -> bool:
    return _detailed


def safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: "[REDACTED]" if key.lower() in SENSITIVE else safe(item)
                for key, item in value.items()}
    if isinstance(value, list):
        return [safe(item) for item in value]
    return value


def table(title: str, columns: list[str], rows: list[list[str]]) -> None:
    view = Table(title=title, box=box.ASCII, expand=False, show_lines=False)
    for column in columns:
        view.add_column(column, overflow="fold")
    for row in rows:
        view.add_row(*row)
    console.print(view)


def status(label: str, state: str, message: str = "") -> None:
    text = Text(f"{state:7} {label}", style=STYLES.get(state, "white"))
    if message:
        text.append(f"  {message}", style="default")
    console.print(text)


def heading(command: str, step: str | None = None) -> None:
    if not _detailed:
        console.rule(f"APIAddicts | {command}" + (f" | {step}" if step else ""), characters="-")


@contextmanager
def phase(label: str, expected_rate_limit: bool = False,
          observed_codes: list[int] | None = None) -> Iterator[None]:
    if _detailed:
        yield
        return
    started = time.perf_counter()
    status(label, "INFO", "en curso")
    try:
        with console.status(Text(label), spinner="line", refresh_per_second=4):
            yield
    except BaseException as error:
        state = "WARN" if expected_rate_limit and is_expected_rate_limit(error, observed_codes) else "FAIL"
        status(label, state, f"{time.perf_counter() - started:.1f}s")
        raise
    else:
        status(label, "PASS", f"{time.perf_counter() - started:.1f}s")


async def wait_window(seconds: int, label: str) -> None:
    if _detailed or not console.is_terminal:
        if not _detailed:
            status(label, "INFO", f"{seconds}s; ventana de rate limit")
        await asyncio.sleep(seconds)
        return
    with Progress(TextColumn("{task.description}"), BarColumn(bar_width=24), TimeRemainingColumn(),
                  console=console, transient=False) as progress:
        task = progress.add_task(label, total=seconds)
        deadline = time.monotonic() + seconds
        while (remaining := deadline - time.monotonic()) > 0:
            await asyncio.sleep(min(0.2, remaining))
            progress.update(task, completed=min(seconds, seconds - max(0, deadline - time.monotonic())))
        progress.update(task, completed=seconds)


def is_expected_rate_limit(error: BaseException | None, observed_codes: list[int] | None = None) -> bool:
    if observed_codes is not None and any(code >= 400 and code != 429 for code in observed_codes):
        return False
    if isinstance(error, BaseExceptionGroup):
        return all(is_expected_rate_limit(child, observed_codes) for child in error.exceptions)
    if isinstance(error, (anyio.BrokenResourceError, anyio.EndOfStream)):
        return observed_codes is not None and 429 in observed_codes
    return isinstance(error, httpx.HTTPStatusError) and error.response.status_code == 429


class ExpectedRateLimitFilter(logging.Filter):
    def filter(self, entry: logging.LogRecord) -> bool:
        error = entry.exc_info[1] if entry.exc_info else None
        return not is_expected_rate_limit(error)


@contextmanager
def expected_rate_limits() -> Iterator[None]:
    if _detailed:
        yield
        return
    logger = logging.getLogger("mcp.client.streamable_http")
    expected = ExpectedRateLimitFilter()
    logger.addFilter(expected)
    try:
        yield
    finally:
        logger.removeFilter(expected)


def mcp_result(payload: dict[str, Any], tool: str | None = None) -> None:
    if _detailed:
        console.print(json.dumps(safe(payload), indent=2), soft_wrap=True)
        return
    initialization = payload.get("initialize", {})
    server = initialization.get("serverInfo", {}).get("name", "MCP")
    protocol = initialization.get("protocolVersion", "?")
    status(server, "PASS", f"protocolo {protocol}")
    result = payload.get("result", {})
    if result.get("isError"):
        status(tool or "MCP", "FAIL", "La herramienta devolvio isError; consultar el JSON guardado")
        return
    if "tools" in result:
        rows = []
        for item in result["tools"]:
            schema = item.get("inputSchema", {})
            required = schema.get("required", [])
            parameters = ", ".join(name + ("*" if name in required else "?")
                                   for name in schema.get("properties", {})) or "Sin parametros"
            rows.append([item["name"], parameters, item.get("description", "")])
        table(f"{len(rows)} herramientas | {server}", ["Herramienta", "Parametros", "Descripcion"], rows)
        return
    value = result.get("structuredContent")
    if value is None:
        text = next((item.get("text", "") for item in result.get("content", [])
                     if item.get("type") == "text"), "")
        try:
            value = json.loads(text)
        except (ValueError, TypeError):
            value = text
    if isinstance(value, dict) and "services" in value:
        table("Servicios encontrados", ["ID", "Categoria", "Clasificacion", "Version"], [
            [str(item.get(key, "")) for key in ["id", "category", "classification", "version"]]
            for item in value["services"]
        ])
    elif isinstance(value, dict) and isinstance(value.get("contract"), dict):
        contract = value["contract"]
        table("Contrato del servicio", ["Campo", "Valor"], [
            ["Servicio", str(value.get("service_id", ""))],
            ["Version", str(value.get("version", ""))],
            ["OpenAPI", str(contract.get("openapi", ""))],
            ["Operaciones", "\n".join(f"{method.upper()} {path}" for path, operations in contract.get("paths", {}).items()
                                      for method in operations if method in {"get", "post", "put", "delete", "patch"})],
            ["Alcance", "Contrato ilustrativo de demo; no endpoint de negocio real"],
        ])
    else:
        table(tool or "Resultado MCP", ["Resultado"], [[json.dumps(safe(value), indent=2)]])


def record(identifier: str, state: str, details: Any) -> None:
    if _detailed:
        console.print(f"{state:7} {identifier}: {json.dumps(safe(details), ensure_ascii=True)}", soft_wrap=True)
        return
    status(identifier, state)
    if not isinstance(details, dict):
        console.print(str(safe(details)))
        return
    if "rows" in details and isinstance(details["rows"], list):
        table("Trazas MCP reales", ["UTC", "Herramienta", "HTTP", "Latencia ms"], [
            [str(item.get(key, "")) for key in ["TimeGenerated", "tool", "ResultCode", "durationMs"]]
            for item in details["rows"]
        ])
        return
    rows = []
    for key, value in safe(details).items():
        if key == "http_codes":
            value = ", ".join(f"HTTP {code}: {count}" for code, count in sorted(Counter(value).items()))
        elif key == "tools":
            value = "\n".join(f"{name}: {', '.join(tools)}" for name, tools in value.items())
        elif key == "resources":
            actions = Counter(action for item in value for action in item.get("actions", []))
            value = ", ".join(f"{action}: {count}" for action, count in sorted(actions.items()))
        elif key == "target":
            value = value.get("name", "Azure")
        elif key == "prices":
            value = f"{value['indicative_max_active_daily_usd']:.2f} USD/dia indicativos; no coste total garantizado"
        elif key == "aca_usage":
            value = "\n".join(f"{item['name']['localizedValue']}: {item.get('currentValue', 0)}/{item['limit']}"
                              for item in value)
        elif isinstance(value, float):
            value = f"{value:.2f}"
        elif isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=True)
        rows.append([key.replace("_", " "), str(value)])
    table("Resumen", ["Comprobacion", "Resultado"], rows)