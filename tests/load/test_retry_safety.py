import inspect

from scripts.demo.demonstrate import load


def test_load_is_bounded_and_never_mutates():
    source = inspect.getsource(load)
    assert "range(12)" in source
    assert 'len(codes) >= burst_budget' in source
    assert 'min(workshop.get("rate_limit_calls", 5) + 6, 25)' in source
    assert 'call_tool("get_service"' in source
    assert "create_access_request" not in source
    assert '429 not in codes' in source
    assert 'recovered["result"]["isError"]' in source