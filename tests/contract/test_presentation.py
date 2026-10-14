import io
import json
import logging
from contextlib import asynccontextmanager

import anyio
import httpx
import pytest
from rich.console import Console

from scripts.lib import presentation
from scripts.lib.workshop import Blocked


@pytest.fixture
def screen(monkeypatch):
    stream = io.StringIO()
    monkeypatch.setattr(presentation, "console", Console(file=stream, width=120, highlight=False, markup=False))
    presentation.configure()
    yield stream
    presentation.configure()


def test_discovery_is_table_not_duplicate_sdk_content(screen):
    payload = {"initialize": {"protocolVersion": "2025-11-25", "serverInfo": {"name": "catalog"}},
               "result": {"tools": [{"name": "get_service", "description": "Read demo service",
               "inputSchema": {"properties": {"service_id": {}}, "required": ["service_id"]}}]}}
    presentation.mcp_result(payload)
    text = screen.getvalue()
    assert "1 herramientas" in text
    assert "get_service" in text
    assert "service_id*" in text
    assert "2025-11-25" in text
    assert "inputSchema" not in text


def test_record_summarizes_rate_limit_and_does_not_display_auth(screen):
    presentation.record("GOV-LOAD", "PASS", {"http_codes": [200, 200, 429], "p95_ms": 1035.4,
                        "headers": {"Ocp-Apim-Subscription-Key": "synthetic-secret"}})
    text = screen.getvalue()
    assert "HTTP 200: 2" in text
    assert "HTTP 429: 1" in text
    assert "1035.40" in text
    assert "synthetic-secret" not in text


def test_detailed_mode_preserves_json_contract(screen):
    presentation.configure(detailed=True)
    payload = {"initialize": {}, "result": {"structuredContent": {"id": "payments"}}}
    presentation.mcp_result(payload, "get_service")
    assert json.loads(screen.getvalue()) == payload


def test_detailed_json_preserves_long_strings_in_narrow_terminal(screen, monkeypatch):
    monkeypatch.setattr(presentation, "console", Console(file=screen, width=30, highlight=False, markup=False))
    presentation.configure(detailed=True)
    payload = {"result": {"endpoint": "https://example.invalid/" + "long-path-" * 40,
                          "content": "quoted \"value\" and literal [markup] " * 20}}
    presentation.mcp_result(payload)
    assert json.loads(screen.getvalue()) == payload


def test_detailed_record_preserves_long_json_value(screen):
    presentation.configure(detailed=True)
    details = {"endpoint": "https://example.invalid/" + "long-path-" * 40}
    presentation.record("GATEWAY", "PASS", details)
    assert json.loads(screen.getvalue().split(": ", 1)[1]) == details


def test_failed_phase_cannot_be_marked_pass(screen):
    with pytest.raises(ValueError), presentation.phase("MCP discovery"):
        raise ValueError("Synthetic failure")
    assert "FAIL" in screen.getvalue()
    assert "PASS" not in screen.getvalue()


def test_expected_rate_limit_phase_warns_and_keeps_error_for_caller(screen):
    request = httpx.Request("POST", "https://example.invalid/mcp")
    error = httpx.HTTPStatusError("Synthetic 429", request=request,
                                   response=httpx.Response(429, request=request))
    with pytest.raises(httpx.HTTPStatusError), presentation.phase("Carga MCP", expected_rate_limit=True):
        raise error
    assert "WARN" in screen.getvalue()
    assert "FAIL" not in screen.getvalue()


def test_unexpected_error_during_rate_limit_phase_still_fails(screen):
    with pytest.raises(ValueError), presentation.phase("Carga MCP", expected_rate_limit=True):
        raise ValueError("Unexpected failure")
    assert "FAIL" in screen.getvalue()
    assert "WARN" not in screen.getvalue()


async def test_redirected_wait_keeps_original_duration(screen, monkeypatch):
    delays = []

    async def sleeping(seconds):
        delays.append(seconds)

    monkeypatch.setattr(presentation.asyncio, "sleep", sleeping)
    await presentation.wait_window(31, "Recuperacion")
    assert delays == [31]
    assert "31s" in screen.getvalue()


async def test_interactive_wait_renders_progress_without_changing_window(screen, monkeypatch):
    monkeypatch.setattr(presentation, "console", Console(file=screen, width=80, force_terminal=True,
                                                         highlight=False, markup=False))
    elapsed = [0.0]

    async def sleeping(seconds):
        elapsed[0] += seconds

    monkeypatch.setattr(presentation.time, "monotonic", lambda: elapsed[0])
    monkeypatch.setattr(presentation.asyncio, "sleep", sleeping)
    await presentation.wait_window(2, "Recuperar ventana APIM")
    assert elapsed[0] == pytest.approx(2)
    assert "Recuperar ventana APIM" in screen.getvalue()


def test_only_expected_rate_limit_tracebacks_are_filtered(screen):
    request = httpx.Request("POST", "https://example.invalid/mcp")
    filter_rule = presentation.ExpectedRateLimitFilter()
    for code in [429, 500, 401]:
        error = httpx.HTTPStatusError("Synthetic response", request=request,
                                      response=httpx.Response(code, request=request))
        entry = logging.LogRecord("mcp.client.streamable_http", logging.ERROR, "", 0, "test", (),
                                  (type(error), error, None))
        assert filter_rule.filter(entry) is (code != 429)
    logger = logging.getLogger("mcp.client.streamable_http")
    before = list(logger.filters)
    with presentation.expected_rate_limits():
        assert len(logger.filters) == len(before) + 1
    assert logger.filters == before


def test_nested_rate_limits_are_filtered_but_mixed_failures_remain_visible(screen):
    request = httpx.Request("POST", "https://example.invalid/mcp")
    limited = httpx.HTTPStatusError("Synthetic 429", request=request,
                                     response=httpx.Response(429, request=request))
    for error, visible in [
        (ExceptionGroup("Expected", [ExceptionGroup("Nested", [limited])]), False),
        (ExceptionGroup("Mixed", [limited, ValueError("Unexpected failure")]), True),
    ]:
        entry = logging.LogRecord("mcp.client.streamable_http", logging.ERROR, "", 0, "test", (),
                                  (type(error), error, None))
        assert presentation.ExpectedRateLimitFilter().filter(entry) is visible


def test_closed_stream_requires_rate_limit_evidence_from_current_attempt(screen):
    error = ExceptionGroup("Closed transport", [anyio.BrokenResourceError()])
    assert not presentation.is_expected_rate_limit(error)
    assert not presentation.is_expected_rate_limit(error, [200])
    assert presentation.is_expected_rate_limit(error, [200, 429])
    assert not presentation.is_expected_rate_limit(error, [429, 500])
    with pytest.raises(ExceptionGroup), presentation.phase("Carga", expected_rate_limit=True,
                                                          observed_codes=[200, 429]):
        raise error
    assert "WARN" in screen.getvalue()
    assert "FAIL" not in screen.getvalue()


def test_contract_view_is_compact_and_marks_demo_scope(screen):
    presentation.mcp_result({"initialize": {}, "result": {"structuredContent": {
        "service_id": "orders", "version": "1.1.0", "contract": {
            "openapi": "3.0.3", "paths": {"/demo/orders": {"get": {"responses": {"200": {}}}}}
        }}}}, "get_service_contract")
    text = screen.getvalue()
    assert "GET /demo/orders" in text
    assert "no endpoint de negocio real" in text
    assert "responses" not in text


async def test_load_does_not_hide_server_failure_after_prior_rate_limit(screen, monkeypatch):
    from scripts.demo import demonstrate

    codes = iter([429, 500])

    async def no_wait(*args):
        pass

    @asynccontextmanager
    async def transport(url, *, httpx_client_factory, **kwargs):
        async with httpx_client_factory() as client:
            request = httpx.Request("POST", url)
            response = httpx.Response(next(codes), request=request)
            for callback in client.event_hooks["response"]:
                await callback(response)
            response.raise_for_status()
            yield None, None, None

    monkeypatch.setattr(demonstrate, "keys", lambda _: {"reader": "synthetic-test-key"})
    monkeypatch.setattr(presentation, "wait_window", no_wait)
    monkeypatch.setattr(demonstrate, "streamablehttp_client", transport)
    workshop = {"gateway_endpoints": {"mcp-catalog": "https://example.invalid/mcp"}}
    with pytest.raises(Blocked, match="Unexpected MCP load failure"):
        await demonstrate.load(workshop)
    text = screen.getvalue()
    assert "WARN" in text
    assert "FAIL" in text
    assert "synthetic-test-key" not in text