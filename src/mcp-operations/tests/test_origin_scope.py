import pytest

from shared.runtime import OriginAuth


def test_read_only_origin_has_no_write_secret(monkeypatch):
    monkeypatch.setenv("REQUIRE_AUTH", "1")
    monkeypatch.setenv("BACKEND_READ_TOKEN", "synthetic-read")
    monkeypatch.delenv("BACKEND_WRITE_TOKEN", raising=False)
    assert OriginAuth(lambda *_: None, "reader").required
    with pytest.raises(RuntimeError, match="write credential"):
        OriginAuth(lambda *_: None, "operator")