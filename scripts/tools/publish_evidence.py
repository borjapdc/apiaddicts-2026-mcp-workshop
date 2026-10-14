import json

from scripts.lib.workshop import LOCAL, ROOT, write_json


def main() -> None:
    records = json.loads((LOCAL / "evidence.json").read_text())
    allowed = {"PREFLIGHT", "LOCAL", "IMAGES", "BACKENDS", "GATEWAY", "GOV-LOAD", "OBS", "VERIFICATION"}
    selected = {name: result for name, result in records.items()
                if name in allowed or name.startswith(("PLAN-", "DRIFT-", "CLEAN-"))}
    write_json(ROOT / "docs/evidence/run.json", selected)
    if (LOCAL / "workshop.json").exists():
        config = json.loads((LOCAL / "workshop.json").read_text())
        write_json(ROOT / "docs/evidence/endpoints.json", {
            "target": config["target"], "foundation": config["foundation"],
            "backends": config["backends"], "gateway_endpoints": config["gateway_endpoints"],
            "rest_url": config["rest_url"], "warning": "URLs contain no keys; live status must be checked"})
    for port in [8002, 8003]:
        source = LOCAL / f"local-tools-{port}.json"
        if source.exists():
            write_json(ROOT / f"docs/fixtures/local-tools-{port}.json", {
                "artifact": "Observed local execution snapshot, not live Azure telemetry",
                "source": f"scripts/tests/test-local.sh --smoke localhost:{port}",
                "result": json.loads(source.read_text())})
    report = LOCAL / "pytest.xml"
    if report.exists():
        (ROOT / "docs/evidence/pytest.xml").write_bytes(report.read_bytes())
    print("PASS evidence published without Terraform state, tfvars or credentials")


if __name__ == "__main__":
    main()