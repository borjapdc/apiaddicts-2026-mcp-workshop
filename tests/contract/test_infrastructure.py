import json
from pathlib import Path
from xml.etree import ElementTree


def test_real_openapi_operations_and_no_mutation_mapping():
    contract = json.loads(Path("infra/terraform/gateway/catalog.openapi.json").read_text())
    operations = {operation["operationId"] for item in contract["paths"].values() for operation in item.values()}
    assert {"search_services", "get_service", "list_versions", "get_service_contract", "create_access_request"} <= operations
    assert contract["openapi"] == "3.0.3"
    main = Path("infra/terraform/gateway/main.tf").read_text()
    tools = main.split("  tools = {", 1)[1].split("\n  }", 1)[0]
    assert "create_access_request" not in tools


def test_policies_are_xml_and_do_not_touch_response_bodies():
    for file in Path("infra/terraform/gateway/policies").iterdir():
        policy = file.read_text()
        for key, value in {"product": "reader", "calls": "5", "period": "30", "origin_secret": "origin-read"}.items():
            policy = policy.replace("${" + key + "}", value)
        assert ElementTree.fromstring(policy).tag == "policies"
        assert "context.Response.Body" not in policy
        assert 'buffer-response="false"' in policy


def test_subscription_header_survives_only_internal_rest_mcp_hop():
    root = Path("infra/terraform/gateway/policies")
    native = ElementTree.fromstring((root / "mcp.xml.tftpl").read_text())
    converted = ElementTree.fromstring((root / "rest-mcp.xml.tftpl").read_text())
    assert native.find("./inbound/set-header[@name='Ocp-Apim-Subscription-Key']") is not None
    assert converted.find("./inbound/set-header[@name='Ocp-Apim-Subscription-Key']") is None
    rest = ElementTree.fromstring((root / "rest.xml").read_text())
    assert rest.find("./inbound/set-header[@name='Ocp-Apim-Subscription-Key']") is not None