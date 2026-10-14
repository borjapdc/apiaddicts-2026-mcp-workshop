import httpx
import pytest

from shared.runtime import catalog_request


@pytest.mark.parametrize("method,expected", [("GET", 3), ("POST", 1)])
async def test_timeout_only_retries_reads(monkeypatch, method, expected):
    calls = []

    async def request(self, *args, **kwargs):
        calls.append(args)
        raise httpx.ReadTimeout("synthetic timeout")

    monkeypatch.setattr(httpx.AsyncClient, "request", request)
    with pytest.raises(RuntimeError, match="timed out"):
        await catalog_request(method, "/api/services")
    assert len(calls) == expected