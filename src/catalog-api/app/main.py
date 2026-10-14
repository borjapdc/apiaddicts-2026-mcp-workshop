import hashlib
import json
import os
import sqlite3
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, Field

from shared.runtime import OriginAuth


class Service(BaseModel):
    id: str
    name: str
    description: str
    owner: str
    category: str
    classification: Literal["internal", "restricted"]
    version: str
    demo_sla_percent: float
    sla_notice: str = "Fictitious demo SLA; not a contractual commitment"
    tags: list[str]
    publication_status: Literal["published", "draft"]


class AccessRequest(BaseModel):
    service_id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,39}$")
    consumer_id: str = Field(pattern=r"^demo-[a-z0-9-]{1,40}$")
    purpose: str = Field(min_length=10, max_length=240, pattern=r"^[^\x00-\x1f]+$")


class AccessReceipt(AccessRequest):
    request_id: str
    status: Literal["demo-pending"] = "demo-pending"
    notice: str = "Fictitious request only; not real authorization"
    storage: str = "Single replica SQLite; ephemeral across revisions/restarts, not production persistence"


SEED = [
    Service(
        id=identifier,
        name=f"{identifier.title()} API",
        description=description,
        owner=f"Demo {category.title()} Team",
        category=category,
        classification="restricted" if identifier in {"payments", "identity"} else "internal",
        version="1.1.0",
        demo_sla_percent=99.5,
        tags=[category, "synthetic", "rest"],
        publication_status="published",
    )
    for identifier, category, description in [
        ("payments", "finance", "Synthetic payment status and settlement catalog"),
        ("inventory", "supply", "Synthetic stock availability catalog"),
        ("orders", "commerce", "Synthetic order lifecycle catalog"),
        ("identity", "security", "Synthetic identity service catalog without personal data"),
        ("shipping", "supply", "Synthetic shipment tracking catalog"),
    ]
]
api = FastAPI(title="Corporate Demo Catalog", version="1.0.0", openapi_version="3.0.3")
database = Path(os.getenv("CATALOG_DB", "/tmp/apiaddicts-catalog.db"))


def find_service(service_id: str) -> Service:
    for service in SEED:
        if service.id == service_id:
            return service
    raise HTTPException(404, "Service not found")


@api.get("/health", operation_id="health")
def health() -> dict[str, str]:
    return {"status": "healthy", "service": "catalog-api"}


@api.get("/api/services", response_model=list[Service], operation_id="search_services")
def search_services(
    query: Annotated[str, Query(max_length=120)] = "",
    category: Annotated[str | None, Query(max_length=40)] = None,
    limit: Annotated[int, Query(ge=1, le=20)] = 10,
) -> list[Service]:
    return [
        service for service in SEED
        if query.lower() in f"{service.id} {service.description} {' '.join(service.tags)}".lower()
        and (category is None or category == service.category)
    ][:limit]


@api.get("/api/services/{service_id}", response_model=Service, operation_id="get_service")
def get_service(service_id: str) -> Service:
    return find_service(service_id)


@api.get("/api/services/{service_id}/versions", operation_id="list_versions")
def list_versions(service_id: str) -> dict[str, object]:
    find_service(service_id)
    return {"service_id": service_id, "versions": ["1.0.0", "1.1.0"], "demo": True}


@api.get("/api/services/{service_id}/contract", operation_id="get_service_contract")
def get_service_contract(service_id: str) -> dict[str, object]:
    service = find_service(service_id)
    return {
        "service_id": service.id, "version": service.version, "demo": True,
        "contract": {"openapi": "3.0.3", "info": {"title": service.name, "version": service.version},
                     "paths": {f"/demo/{service_id}": {"get": {"responses": {"200": {
                         "description": "Fictitious business response; endpoint not implemented"}}}}}},
    }


@api.post("/api/access-requests", response_model=AccessReceipt, status_code=201,
          operation_id="create_access_request")
def create_access_request(request: AccessRequest, response: Response) -> AccessReceipt:
    find_service(request.service_id)
    payload = request.model_dump_json()
    request_id = "demo-" + hashlib.sha256(payload.encode()).hexdigest()[:24]
    database.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database, timeout=5) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        cursor = connection.execute("INSERT OR IGNORE INTO requests VALUES (?, ?)", (request_id, payload))
        if cursor.rowcount == 0:
            response.status_code = 200
    return AccessReceipt(**json.loads(payload), request_id=request_id)


app = OriginAuth(api, "catalog")