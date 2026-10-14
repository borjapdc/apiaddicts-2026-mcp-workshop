import argparse
import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import hcl2
import httpx

from scripts.lib import presentation
from shared.runtime import load_app

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / ".local"
INFRA = ROOT / "infra/terraform"
SERVICES = ["catalog-api", "mcp-catalog", "mcp-operations"]
ENTRYPOINT_GROUPS = {
    "demo": "demo", "local": "demo", "load": "demo", "observe": "demo",
    "preflight": "terraform", "deploy": "terraform", "destroy": "terraform",
    "assert-subscription": "terraform",
    "test-local": "tests", "test-azure": "tests", "test-backends": "tests",
    "configure-mcp": "tools", "credentials": "tools",
}
PROVIDERS = ["Microsoft.App", "Microsoft.ApiManagement", "Microsoft.ContainerRegistry",
             "Microsoft.OperationalInsights", "Microsoft.Insights", "Microsoft.ManagedIdentity",
             "Microsoft.Authorization"]


class Blocked(RuntimeError):
    pass


def write_json(path: Path, value: Any, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if private and not path.exists():
        descriptor = os.open(path, os.O_CREAT | os.O_WRONLY, 0o600)
        os.close(descriptor)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    if private and os.name != "nt":
        path.chmod(0o600)


def run(*command: str, capture: bool = False, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=capture, check=False)
    if check and result.returncode:
        raise Blocked(f"Command failed ({result.returncode}): {command[0]} {command[1] if len(command) > 1 else ''}")
    return result


def az(*args: str) -> Any:
    result = run("az", *args, "--output", "json", "--only-show-errors", capture=True)
    return json.loads(result.stdout or "null")


def record(identifier: str, status: str, command: str, details: Any) -> None:
    path = LOCAL / "evidence.json"
    records = json.loads(path.read_text()) if path.exists() else {}
    records[identifier] = {"status": status, "command": command, "details": details,
                           "timestamp": datetime.now(UTC).isoformat()}
    write_json(path, records, private=True)
    presentation.record(identifier, status, details)


def choose_subscription(accounts: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [account for account in accounts
                  if account["state"] == "Enabled" and "mvp" in account["name"].lower()]
    if len(candidates) != 1:
        names = [{"name": item["name"], "id": item["id"][:8] + "..."} for item in candidates]
        raise Blocked(f"MVP selection is not unique: {names}; human decision required")
    return {key: candidates[0][key] for key in ["name", "id", "tenantId"]}


def assert_subscription() -> dict[str, Any]:
    target = choose_subscription(az("account", "list", "--all"))
    remembered = LOCAL / "target.json"
    if remembered.exists():
        previous = json.loads(remembered.read_text())
        if previous["id"] != target["id"] or previous["tenantId"] != target["tenantId"]:
            raise Blocked("Previously recorded target differs; never switch an existing state to another subscription")
    run("az", "account", "set", "--subscription", target["id"], capture=True)
    actual = az("account", "show", "--subscription", target["id"])
    if actual["id"] != target["id"] or actual["tenantId"] != target["tenantId"]:
        raise Blocked("Azure context does not match selected MVP")
    write_json(remembered, target, private=True)
    return target


def settings() -> dict[str, Any]:
    path = INFRA / "foundation/terraform.tfvars"
    if not path.exists():
        path = INFRA / "foundation/terraform.tfvars.example"
    with path.open() as stream:
        return dict(hcl2.load(stream))


def prices(location: str) -> dict[str, Any]:
    cache_path = LOCAL / "costs.json"
    evidence_path = LOCAL / "evidence.json"
    if cache_path.exists():
        cached = json.loads(cache_path.read_text())
        checked_at = cached.get("checked_at_utc")
        if not checked_at and evidence_path.exists():
            checked_at = json.loads(evidence_path.read_text()).get("PREFLIGHT", {}).get("timestamp")
        if checked_at:
            age = (datetime.now(UTC) - datetime.fromisoformat(checked_at)).total_seconds()
            meters = cached.get("meters", [])
            if (0 <= age <= 21600 and len(meters) == 5
                    and cached.get("source") == "https://prices.azure.com/api/retail/prices"
                    and all(item["armRegionName"] == location and item["currencyCode"] == "USD" for item in meters)):
                print(f"WARN    COST verified official regional cache ({age / 3600:.2f}h old); remove .local/costs.json to force refresh")
                return {**cached, "checked_at_utc": checked_at, "cache_age_hours": round(age / 3600, 3)}
    return fresh_prices(location)


def fresh_prices(location: str) -> dict[str, Any]:
    selected = []
    meters = [("API Management", "Developer Unit"), ("Container Registry", "Basic Registry Unit"),
              ("Azure Container Apps", "Standard vCPU Active Usage"),
              ("Azure Container Apps", "Standard Memory Active Usage"),
              ("Log Analytics", "Analytics Logs Data Ingestion")]
    with httpx.Client(timeout=30) as client:
        for service, meter in meters:
            response = client.get("https://prices.azure.com/api/retail/prices", params={
                "$filter": f"armRegionName eq '{location}' and serviceName eq '{service}' and priceType eq 'Consumption'"
            })
            response.raise_for_status()
            rows = [item for item in response.json()["Items"]
                    if item["meterName"] == meter and item["retailPrice"] > 0]
            if not rows:
                raise Blocked(f"Regional price missing for {service}; cost gate cannot be bounded")
            item = rows[0]
            selected.append({key: item[key] for key in ["serviceName", "meterName", "retailPrice", "unitOfMeasure", "currencyCode", "armRegionName"]})
    by_service = {item["serviceName"]: item["retailPrice"] for item in selected}
    by_meter = {item["meterName"]: item["retailPrice"] for item in selected}
    daily = (24 * by_service["API Management"] + by_service["Container Registry"]
             + 86400 * (1.25 * by_meter["Standard vCPU Active Usage"] + 2.5 * by_meter["Standard Memory Active Usage"])
             + 0.1 * by_service["Log Analytics"])
    return {"source": "https://prices.azure.com/api/retail/prices", "meters": selected,
            "checked_at_utc": datetime.now(UTC).isoformat(),
            "indicative_max_active_daily_usd": round(daily, 4),
            "notice": "Indicative consumption estimate, not hard budget; excludes builds, excess storage, requests, egress and taxes; TTL does not delete resources"}


def preflight(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    for tool in ["az", "terraform", "uv", "dotnet"]:
        if not shutil.which(tool):
            raise Blocked(f"Missing prerequisite: {tool}")
        print(f"PASS    TOOL {tool}")
    target = assert_subscription()
    config = settings()
    for key, detected in [("subscription_id", target["id"]), ("tenant_id", target["tenantId"])]:
        if config.get(key) not in [None, detected, "00000000-0000-0000-0000-000000000000"]:
            raise Blocked(f"{key} in tfvars differs from selected MVP")
        config[key] = detected
    if args.location:
        config["location"] = args.location
    subscription = target["id"]
    registered = az("provider", "list", "--subscription", subscription)
    states = {item["namespace"].lower(): item["registrationState"] for item in registered}
    for provider in PROVIDERS:
        if states.get(provider.lower()) != "Registered":
            raise Blocked(f"Provider {provider} not Registered; registration permission/action required")
        print(f"PASS    PROVIDER {provider}")
    prefix = f"https://management.azure.com/subscriptions/{subscription}"
    permissions = az("rest", "--method", "get", "--url", prefix + "/providers/Microsoft.Authorization/permissions?api-version=2022-04-01")
    if not any("*" in entry["actions"] and not entry.get("notActions") for entry in permissions["value"]):
        raise Blocked("Automated permission gate requires unambiguous create and RBAC rights; inspect RG-scope roles manually")
    usage = az("rest", "--method", "get", "--url", prefix + f"/providers/Microsoft.App/locations/{config['location']}/usages?api-version=2025-07-01")
    environment = next((item for item in usage["value"] if item["name"]["value"] == "ManagedEnvironmentCount"), None)
    if not environment or environment["currentValue"] >= environment["limit"]:
        raise Blocked("Regional ACA managed environment quota unavailable/exhausted")
    skus = az("rest", "--method", "get", "--url", prefix + "/providers/Microsoft.ApiManagement/skus?api-version=2024-05-01")
    available = [item for item in skus["value"] if item["name"] == config["apim_sku"]
                 and config["location"] in item["locations"] and not item.get("restrictions")]
    if not available:
        raise Blocked("Requested APIM SKU unavailable in selected subscription/region")
    if config["apim_sku"] != "Developer":
        raise Blocked("BasicV2 needs separate explicit price validation; never replace a Developer instance automatically")
    acr_count = len(az("acr", "list", "--subscription", subscription))
    if acr_count >= 250:
        raise Blocked("ACR subscription limit reached")
    price = prices(config["location"])
    if price["indicative_max_active_daily_usd"] > args.daily_budget_usd:
        raise Blocked(f"Indicative daily compute/ingestion estimate exceeds {args.daily_budget_usd} USD gate")
    record("PREFLIGHT", "PASS", "scripts/terraform/preflight.sh", {
        "target": target, "location": config["location"], "aca_usage": usage["value"],
        "apim_sku": config["apim_sku"], "acr_count": acr_count, "prices": price,
        "warning": "ACA per-environment CPU and final provisioning capacity still need workload verification"})
    write_json(LOCAL / "costs.json", price)
    write_json(INFRA / "foundation/detected.auto.tfvars.json", config, private=True)
    return target, config


def terraform(module: str, *args: str, capture: bool = False, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run("terraform", f"-chdir={INFRA / module}", *args, capture=capture, check=check)


def output(module: str) -> dict[str, Any]:
    result = terraform(module, "output", "-json", capture=True)
    return {key: value["value"] for key, value in json.loads(result.stdout).items()}


def scope_plan(plan: dict[str, Any], target: dict[str, Any], group: str | None, destroy: bool = False) -> None:
    variables = plan.get("variables", {})
    if variables.get("subscription_id", {}).get("value") != target["id"]:
        raise Blocked("Plan subscription mismatch")
    if variables.get("tenant_id", {}).get("value") != target["tenantId"]:
        raise Blocked("Plan tenant mismatch")
    for change in plan.get("resource_changes", []):
        if change.get("mode") == "data":
            continue
        actions = change["change"]["actions"]
        if "delete" in actions and not destroy:
            raise Blocked(f"Replacement/deletion needs review: {change['address']}")
        values = change["change"].get("before" if destroy else "after") or {}
        resource_id = values.get("id", "") or ""
        if resource_id.startswith("/subscriptions/") and not resource_id.lower().startswith(f"/subscriptions/{target['id']}/resourcegroups/".lower()):
            raise Blocked(f"Resource outside RG/subscription scope: {change['address']}")
        resource_group = values.get("resource_group_name")
        if resource_group and group and resource_group != group:
            raise Blocked(f"Foreign resource group: {resource_group}")
        if resource_id.startswith("/subscriptions/") and group and f"/resourcegroups/{group}/".lower() not in (resource_id + "/").lower():
            raise Blocked(f"Foreign resource ID: {change['address']}")
        if change["type"] == "azurerm_resource_group":
            name = values.get("name", "") or ""
            if name and (not name.startswith("rg-") or "apiaddicts" not in name):
                raise Blocked("RG name is not workshop-owned")


def stage(module: str, target: dict[str, Any], apply: bool, group: str | None = None) -> None:
    terraform(module, "init", "-input=false")
    terraform(module, "fmt", "-check")
    terraform(module, "validate")
    planfile = LOCAL / f"{module}.tfplan"
    terraform(module, "plan", "-input=false", f"-out={planfile}")
    plan = json.loads(terraform(module, "show", "-json", str(planfile), capture=True).stdout)
    if module == "foundation":
        groups = [item for item in plan.get("resource_changes", []) if item["type"] == "azurerm_resource_group"]
        if groups:
            group = groups[0]["change"].get("after", {}).get("name")
            if apply and not group:
                raise Blocked("Persist the naming suffix before cloud apply")
            if group and "create" in groups[0]["change"]["actions"] and az("group", "exists", "--name", group, "--subscription", target["id"]):
                raise Blocked("The planned new resource group already exists; refusing to adopt foreign resources")
    scope_plan(plan, target, group)
    summary = [{"address": item["address"], "actions": item["change"]["actions"]}
               for item in plan.get("resource_changes", [])]
    record(f"PLAN-{module.upper()}", "PASS", f"terraform -chdir=infra/terraform/{module} plan", {
        "subscription_id": target["id"], "tenant_id": target["tenantId"], "resource_group": group,
        "location": plan.get("variables", {}).get("location", {}).get("value"), "resources": summary})
    if apply:
        print(f"APPLY TARGET {target['name']} {target['id']} tenant={target['tenantId']} RG={group or 'new workshop RG from plan'}")
        terraform(module, "apply", "-input=false", str(planfile))


def content_tag(service: str) -> str:
    paths = [ROOT / "pyproject.toml", ROOT / "uv.lock"]
    paths += sorted((ROOT / "shared").glob("*.py"))
    paths += sorted((ROOT / "src" / service).rglob("*.py"))
    paths += [ROOT / "src" / service / "Dockerfile"]
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(path.read_bytes())
    return "sha-" + digest.hexdigest()[:20]


def deploy(args: argparse.Namespace) -> None:
    target, config = preflight(args)
    if args.apply and not (INFRA / "foundation/terraform.tfstate").exists():
        terraform("foundation", "init", "-input=false")
        print("Persisting Terraform random suffix only; this operation creates no Azure resource")
        terraform("foundation", "apply", "-target=random_string.suffix", "-auto-approve", "-input=false")
    stage("foundation", target, args.apply)
    if not args.apply and not (INFRA / "foundation/terraform.tfstate").exists():
        print("PASS    PLAN ONLY: foundation planned; downstream plans require its real outputs and built images")
        return
    foundation_outputs = output("foundation")
    foundation = foundation_outputs["foundation"]
    group = foundation["resource_group_name"]
    print(json.dumps({"subscription": target, "region": config["location"], "resource_group": group,
                      "costs": json.loads((LOCAL / "costs.json").read_text())}, indent=2))
    images = {}
    for service in SERVICES:
        tag = content_tag(service)
        exists = run("az", "acr", "repository", "show", "--subscription", target["id"],
                     "--name", foundation["acr_name"], "--image", f"{service}:{tag}", "-o", "json",
                     "--only-show-errors", capture=True, check=False)
        if exists.returncode and args.apply:
            run("az", "acr", "build", "--subscription", target["id"], "--registry", foundation["acr_name"],
                "--image", f"{service}:{tag}", "--file", f"src/{service}/Dockerfile", "--timeout", "600",
                "--no-logs", ".")
        elif exists.returncode:
            raise Blocked("Plan-only cannot build missing images; use --apply after reviewing foundation")
        image = az("acr", "repository", "show", "--subscription", target["id"], "--name", foundation["acr_name"],
                   "--image", f"{service}:{tag}")
        images[service] = f"{foundation['acr_login_server']}/{service}@{image['digest']}"
    record("IMAGES", "PASS", "az acr repository show", images)
    linked = {"subscription_id": target["id"], "tenant_id": target["tenantId"], "foundation": foundation,
              "backend_read_token": foundation_outputs["backend_read_token"],
              "backend_write_token": foundation_outputs["backend_write_token"]}
    write_json(INFRA / "workload/linked.auto.tfvars.json", {**linked, "images": images}, private=True)
    stage("workload", target, args.apply, group)
    workload = output("workload")
    if args.apply:
        asyncio.run(backend_smoke(workload["backends"], foundation_outputs))
    write_json(INFRA / "gateway/linked.auto.tfvars.json", {**linked, "backends": workload["backends"],
               "app_insights_instrumentation_key": foundation_outputs["app_insights_instrumentation_key"]}, private=True)
    stage("gateway", target, args.apply, group)
    gateway = output("gateway")
    workshop = {"target": target, "foundation": foundation, "backends": workload["backends"], **gateway}
    write_json(LOCAL / "workshop.json", workshop)
    if args.apply:
        asyncio.run(azure_smoke(workshop))
        for module in ["foundation", "workload", "gateway"]:
            result = terraform(module, "plan", "-input=false", "-detailed-exitcode", capture=True, check=False)
            record(f"DRIFT-{module.upper()}", "PASS" if result.returncode == 0 else "FAIL",
                   f"terraform -chdir=infra/terraform/{module} plan -detailed-exitcode", {"exit_code": result.returncode})
            if result.returncode:
                raise Blocked(f"Unexpected drift in {module}; inspect terraform plan locally")


async def backend_smoke(backends: dict[str, str], secrets: dict[str, Any]) -> None:
    for attempt in range(4):
        try:
            await backend_smoke_once(backends, secrets)
            return
        except (ExceptionGroup, httpx.HTTPError):
            if attempt == 3:
                raise
            await asyncio.sleep(2 ** attempt)


async def backend_smoke_once(backends: dict[str, str], secrets: dict[str, Any]) -> None:
    client = load_app(str(ROOT / "src/mcp-client/client.py"), "backend_client")
    async with httpx.AsyncClient(timeout=15) as transport:
        for name, base in backends.items():
            response = await transport.get(base + "/health")
            response.raise_for_status()
            route = "/api/services" if name == "catalog-api" else "/mcp"
            response = await transport.get(base + route)
            if response.status_code != 401:
                raise Blocked(f"Anonymous origin not rejected: {name} HTTP {response.status_code}")
    for name in ["mcp-catalog", "mcp-operations"]:
        token = secrets["backend_write_token" if name == "mcp-operations" else "backend_read_token"]
        result = await client.invoke(backends[name] + "/mcp", headers={"x-backend-token": token})
        if not result["result"]["tools"]:
            raise Blocked(f"No tools on {name}")
    record("BACKENDS", "PASS", "scripts/tests/test-backends.sh", {"healthy": list(backends), "anonymous_status": 401})


def keys(workshop: dict[str, Any]) -> dict[str, str]:
    result = {}
    for role, identifier in workshop["subscription_ids"].items():
        result[role] = az("rest", "--method", "post", "--url",
                          f"https://management.azure.com{identifier}/listSecrets?api-version=2025-09-01-preview")["primaryKey"]
    return result


async def azure_smoke(workshop: dict[str, Any]) -> None:
    await presentation.wait_window(workshop.get("rate_limit_period_seconds", 30) + 1, "Preparar ventana APIM")
    module = load_app(str(ROOT / "src/mcp-client/client.py"), "azure_client")
    credentials = keys(workshop)
    endpoints = workshop["gateway_endpoints"]
    async with httpx.AsyncClient(timeout=30) as transport:
        for name, url in endpoints.items():
            response = await transport.post(url, json={})
            if response.status_code not in {401, 403}:
                raise Blocked(f"Anonymous APIM request not rejected: {name} HTTP {response.status_code}")
        forbidden = await transport.post(endpoints["mcp-operations"], json={}, headers={"Ocp-Apim-Subscription-Key": credentials["reader"]})
        if forbidden.status_code not in {401, 403}:
            raise Blocked(f"Reader accepted on operator server: HTTP {forbidden.status_code}")
    observed = {}
    for name, url in endpoints.items():
        role = "operator" if name == "mcp-operations" else "reader"
        result = await module.invoke(url, headers={"Ocp-Apim-Subscription-Key": credentials[role]})
        observed[name] = [tool["name"] for tool in result["result"]["tools"]]
    await presentation.wait_window(workshop.get("rate_limit_period_seconds", 30) + 1, "Preparar llamadas equivalentes")
    reader_headers = {"Ocp-Apim-Subscription-Key": credentials["reader"]}
    native = await module.invoke(endpoints["mcp-catalog"], "get_service", {"service_id": "payments"}, reader_headers)
    rest = await module.invoke(endpoints["mcp-catalog-from-rest"], "get_service", {"service_id": "payments"}, reader_headers)
    def unpack(result: dict[str, Any]) -> Any:
        body = result["result"]
        if body.get("isError"):
            raise Blocked("Tool call returned MCP isError")
        if body.get("structuredContent"):
            return body["structuredContent"]
        return json.loads(next(item["text"] for item in body["content"] if item["type"] == "text"))
    if unpack(native).get("id") != "payments" or unpack(rest).get("id") != "payments":
        raise Blocked("Native and REST-backed results do not match the dataset")
    arguments = {"service_id": "orders", "consumer_id": "demo-operator", "purpose": "Synthetic APIAddicts workshop"}
    created = await module.invoke(endpoints["mcp-operations"], "create_access_request", arguments,
                                  {"Ocp-Apim-Subscription-Key": credentials["operator"]})
    if unpack(created).get("status") != "demo-pending":
        raise Blocked("Operator mutation failed")
    record("GATEWAY", "PASS", "scripts/tests/test-azure.sh", {"tools": observed, "reader_write_denied": True,
           "anonymous_denied": True, "equivalent_service": "payments", "operator_mutation": "demo-pending"})


def local_test(args: argparse.Namespace) -> None:
    with presentation.phase("Dependencias bloqueadas"):
        run("uv", "sync", "--frozen")
    with presentation.phase("Lint"):
        run("uv", "run", "ruff", "check", "shared", "src", "scripts", "tests")
    with presentation.phase("Tipos Python"):
        run("uv", "run", "mypy", "shared", "src/mcp-client/client.py", "scripts")
        for service in SERVICES:
            run("uv", "run", "mypy", f"src/{service}/app/main.py")
    with presentation.phase("Tests de contratos, red y seguridad"):
        run("uv", "run", "pytest", "-q", "--junitxml=.local/pytest.xml")
    if args.smoke:
        async def smoke() -> None:
            client = load_app(str(ROOT / "src/mcp-client/client.py"), "local_demo_client")
            async with httpx.AsyncClient(timeout=15) as transport:
                for port in [8001, 8002, 8003]:
                    (await transport.get(f"http://localhost:{port}/health")).raise_for_status()
                (await transport.get("http://localhost:15888")).raise_for_status()
            for port in [8002, 8003]:
                result = await client.invoke(f"http://localhost:{port}/mcp")
                write_json(LOCAL / f"local-tools-{port}.json", result)
            result = await client.invoke("http://localhost:8002/mcp", "get_service_contract", {"service_id": "orders"})
            if result["result"]["isError"]:
                raise Blocked("Local contract invocation failed")
        asyncio.run(smoke())
        record("LOCAL", "PASS", "scripts/tests/test-local.sh --smoke", {"health": [8001, 8002, 8003], "dashboard": 15888})


def destroy(args: argparse.Namespace) -> None:
    target = assert_subscription()
    foundation = output("foundation")["foundation"]
    group = foundation["resource_group_name"]
    if args.apply and (args.confirm_group != group or args.confirm_subscription != target["id"]):
        raise Blocked("Destructive action requires exact --confirm-group AND --confirm-subscription")
    observed = az("group", "show", "--name", group, "--subscription", target["id"])
    if observed.get("tags", {}).get("workshop_instance_id") != foundation["workshop_instance_id"]:
        raise Blocked("Resource group ownership tag mismatch")
    for module in ["gateway", "workload", "foundation"]:
        if not (INFRA / module / "terraform.tfstate").exists():
            continue
        planfile = LOCAL / f"destroy-{module}.tfplan"
        terraform(module, "state", "list")
        terraform(module, "plan", "-destroy", "-input=false", f"-out={planfile}")
        plan = json.loads(terraform(module, "show", "-json", str(planfile), capture=True).stdout)
        scope_plan(plan, target, group, destroy=True)
        record(f"CLEAN-{module.upper()}", "PASS", f"terraform -chdir=infra/terraform/{module} plan -destroy",
               {"group": group, "subscription_id": target["id"], "applied": args.apply})
        if args.apply:
            terraform(module, "apply", "-input=false", str(planfile))
    if args.apply:
        exists = az("group", "exists", "--name", group, "--subscription", target["id"])
        if exists:
            raise Blocked("RG still exists; verify APIM deletion before assuming charges stopped")


def main() -> None:
    parser = argparse.ArgumentParser(description="APIAddicts workshop; plan-only by default. Cloud target must be unique MVP.")
    parser.add_argument("command", choices=["assert-subscription", "preflight", "deploy", "local", "test-local", "test-azure", "test-backends", "demo", "destroy", "configure-mcp", "observe", "load"])
    parser.add_argument("--apply", action="store_true", help="Authorize the reviewed Terraform plans; destroy is destructive")
    parser.add_argument("--what-if", action="store_true", help="Explicit plan-only mode")
    parser.add_argument("--location")
    parser.add_argument("--daily-budget-usd", type=float, default=6.0)
    parser.add_argument("--smoke", action="store_true", help="Also test the already running Aspire containers")
    parser.add_argument("--step", choices=["discover", "cloud", "govern", "foundry"], default="discover")
    parser.add_argument("--confirm-group")
    parser.add_argument("--confirm-subscription")
    parser.add_argument("--json", action="store_true", help="Detailed SDK JSON and evidence output instead of presentation tables")
    args = parser.parse_args()
    os.chdir(ROOT)
    if args.what_if and args.apply:
        parser.error("--what-if and --apply are mutually exclusive")
    presentation.configure(detailed=args.json or os.getenv("WORKSHOP_OUTPUT") == "json")
    if args.command != "assert-subscription":
        presentation.heading(args.command, args.step if args.command == "demo" else None)
    try:
        if args.command == "assert-subscription":
            print(json.dumps(assert_subscription(), indent=2))
        elif args.command == "preflight":
            preflight(args)
        elif args.command == "deploy":
            deploy(args)
        elif args.command == "test-local":
            local_test(args)
        elif args.command == "local":
            executable = shutil.which("aspire") or str(LOCAL / "tools" / ("aspire.exe" if os.name == "nt" else "aspire"))
            run(executable, "run", "--apphost", str(ROOT / "aspire/AppHost/AppHost.csproj"), "--non-interactive")
        elif args.command == "destroy":
            destroy(args)
        elif args.command == "test-backends":
            assert_subscription()
            asyncio.run(backend_smoke(output("workload")["backends"], output("foundation")))
        elif args.command == "test-azure":
            assert_subscription()
            asyncio.run(azure_smoke(json.loads((LOCAL / "workshop.json").read_text())))
        else:
            from scripts.demo.demonstrate import execute
            execute(args)
    except (Blocked, FileNotFoundError, httpx.HTTPError, ExceptionGroup) as error:
        details = str(error) if isinstance(error, Blocked) else f"{type(error).__name__}; inspect prerequisites/readiness, no secrets logged"
        record(args.command.upper(), "BLOCKED", f"scripts/{ENTRYPOINT_GROUPS[args.command]}/{args.command}.sh", {"reason": details})
        sys.exit(2)


if __name__ == "__main__":
    sys.modules["scripts.lib.workshop"] = sys.modules[__name__]
    main()