from mcp.server.transport_security import TransportSecurityMiddleware

from shared.runtime import server_settings


def test_https_host_without_explicit_port(monkeypatch):
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "demo.region.azurecontainerapps.io:*")
    security = TransportSecurityMiddleware(server_settings()["transport_security"])
    assert security._validate_host("demo.region.azurecontainerapps.io")
    assert security._validate_host("demo.region.azurecontainerapps.io:443")
    assert not security._validate_host("attacker.example")