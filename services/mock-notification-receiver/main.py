from __future__ import annotations

import copy
import logging
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Optional

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from configs import settings

logging.basicConfig(level=getattr(logging, str(settings.log_level or "INFO").upper(), logging.INFO))
logger = logging.getLogger("mock_notification_receiver.app")

FHIR_JSON_CONTENT_TYPE = "application/fhir+json"
TASK_EXT_SENDER_BGZ_BASE_URL = "http://example.org/fhir/StructureDefinition/sender-bgz-base"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fhir_json_response(payload: dict[str, Any], *, status_code: int = 200, headers: dict[str, str] | None = None) -> JSONResponse:
    out_headers = dict(headers or {})
    out_headers["Content-Type"] = FHIR_JSON_CONTENT_TYPE
    return JSONResponse(content=payload, status_code=status_code, headers=out_headers)


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        return [part for part in raw.replace(",", " ").split() if part]
    raw = str(value).strip()
    return [raw] if raw else []


def _first_non_empty(data: dict[str, Any], *paths: tuple[str, ...]) -> Any:
    for path in paths:
        cur: Any = data
        ok = True
        for part in path:
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                ok = False
                break
        if ok and cur not in (None, "", [], {}):
            return cur
    return None


def _raise_http(status_code: int, reason: str, message: str, **extra: Any) -> None:
    detail: dict[str, Any] = {"reason": reason, "message": message}
    for key, value in extra.items():
        if value is not None:
            detail[key] = value
    raise HTTPException(status_code=status_code, detail=detail)


@dataclass
class TokenContext:
    raw: dict[str, Any]
    active: bool
    organization_ura: str
    scopes: list[str]


def _extract_token_context(data: dict[str, Any]) -> TokenContext:
    return TokenContext(
        raw=dict(data or {}),
        active=bool(data.get("active") is True or _truthy(data.get("active"))),
        organization_ura=str(
            _first_non_empty(
                data,
                ("organization_ura",),
                ("claims", "organization_ura"),
                ("subject_organization_id",),
                ("subject", "properties", "subject_organization_id"),
                ("organization", "ura"),
            )
            or ""
        ).strip(),
        scopes=_string_list(
            _first_non_empty(
                data,
                ("scope",),
                ("claims", "scope"),
                ("client_qualifications",),
                ("subject", "properties", "client_qualifications"),
            )
        ),
    )


def _join_url(base: str, path: str) -> str:
    return f"{str(base or '').strip().rstrip('/')}/{str(path or '').lstrip('/')}"


async def _introspect_token(token: str) -> TokenContext:
    url = _join_url(settings.nuts_internal_base, "/internal/auth/v2/accesstoken/introspect")
    try:
        response = await app.state.http_client.post(
            url,
            data={"token": token},
            headers={"Accept": "application/json"},
            timeout=settings.introspection_timeout,
        )
    except httpx.HTTPError as exc:
        logger.exception("Notification token introspection failed")
        _raise_http(502, "introspection_failed", "Nuts token introspection faalde.", error=str(exc))

    if response.status_code >= 400:
        _raise_http(
            502,
            "introspection_failed",
            "Nuts token introspection faalde.",
            status_code=response.status_code,
            upstream_body=str(getattr(response, "text", "") or "")[:500] or None,
        )
    try:
        payload = response.json()
    except Exception as exc:
        logger.exception("Notification token introspection did not return JSON")
        _raise_http(502, "introspection_invalid_json", "Nuts token introspection gaf geen geldige JSON terug.", error=str(exc))
    if not isinstance(payload, dict):
        _raise_http(502, "introspection_invalid_json", "Nuts token introspection gaf geen JSON object terug.")

    ctx = _extract_token_context(payload)
    if not ctx.active:
        _raise_http(401, "inactive_token", "Toegangstoken is niet actief of niet geldig.")
    if not ctx.organization_ura:
        _raise_http(403, "missing_organization_ura", "Introspectie mist organization_ura.")

    required_scope = str(settings.required_scope or "").strip()
    if required_scope and required_scope not in set(ctx.scopes):
        _raise_http(
            403,
            "scope_not_allowed",
            "De aangeleverde scope voldoet niet aan de vereiste receiver-scope.",
            required_scope=required_scope,
            received_scopes=ctx.scopes,
        )
    return ctx


def _extract_task_input_value(task: dict[str, Any], code: str) -> Optional[Any]:
    for item in task.get("input") or []:
        if not isinstance(item, dict):
            continue
        coding_list = ((item.get("type") or {}).get("coding") or [])
        if any(isinstance(coding, dict) and str(coding.get("code") or "") == code for coding in coding_list):
            if "valueString" in item:
                return item.get("valueString")
            if "valueBoolean" in item:
                return item.get("valueBoolean")
    return None


def _extract_sender_bgz_base(task: dict[str, Any]) -> Optional[str]:
    for extension in task.get("extension") or []:
        if not isinstance(extension, dict):
            continue
        if str(extension.get("url") or "") == TASK_EXT_SENDER_BGZ_BASE_URL:
            value = str(extension.get("valueUrl") or "").strip()
            if value:
                return value
    return None


def _extract_task_sender_ura(task: dict[str, Any]) -> Optional[str]:
    requester = task.get("requester") or {}
    onbehalfof = requester.get("onBehalfOf") or {}
    identifier = onbehalfof.get("identifier") or {}
    value = str(identifier.get("value") or "").strip()
    return value or None


async def _authorize_notification_request(request: Request, task: dict[str, Any]) -> None:
    if not settings.require_bearer_token:
        return

    auth_header = str(request.headers.get("Authorization") or "").strip()
    if not auth_header.lower().startswith("bearer "):
        _raise_http(401, "missing_bearer_token", "Authorization header met Bearer token is verplicht.")
    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        _raise_http(401, "missing_bearer_token", "Bearer token ontbreekt.")

    token_ctx = await _introspect_token(token)
    task_sender_ura = _extract_task_sender_ura(task)
    if not task_sender_ura:
        _raise_http(
            400,
            "missing_task_sender_ura",
            "Notification Task mist requester.onBehalfOf.identifier.value (sender URA).",
        )
    if token_ctx.organization_ura != task_sender_ura:
        _raise_http(
            403,
            "organization_not_authorized",
            "organization_ura uit introspectie matcht niet met de sender URA in de notification Task.",
            token_organization_ura=token_ctx.organization_ura,
            task_sender_ura=task_sender_ura,
        )


def _task_summary(task: dict[str, Any], *, received_at: str) -> dict[str, Any]:
    owner_identifier = ((task.get("owner") or {}).get("identifier") or {})
    patient_identifier = ((task.get("for") or {}).get("identifier") or {})
    based_on = task.get("basedOn") or []
    first_based_on = based_on[0] if isinstance(based_on, list) and based_on else {}
    return {
        "id": str(task.get("id") or "").strip(),
        "status": str(task.get("status") or "").strip() or None,
        "based_on": str((first_based_on or {}).get("reference") or "").strip() or None,
        "authorization_base": _extract_task_input_value(task, "authorization-base"),
        "get_workflow_task": _extract_task_input_value(task, "get-workflow-task"),
        "sender_bgz_base": _extract_sender_bgz_base(task),
        "owner_ura": str(owner_identifier.get("value") or "").strip() or None,
        "patient_bsn": str(patient_identifier.get("value") or "").strip() or None,
        "sender_ura": _extract_task_sender_ura(task),
        "received_at": received_at,
    }


def _capability_statement() -> dict[str, Any]:
    public_base = str(settings.public_base or "").rstrip("/")
    return {
        "resourceType": "CapabilityStatement",
        "status": "active",
        "date": _now_iso(),
        "kind": "instance",
        "fhirVersion": "3.0.2",
        "format": ["json"],
        "software": {
            "name": "Mock Notification Receiver",
            "version": "0.1.0",
        },
        "implementation": {
            "description": "Barebones receiver mock for local BgZ sender flow testing",
            "url": public_base,
        },
        "rest": [
            {
                "mode": "server",
                "resource": [
                    {
                        "type": "Task",
                        "interaction": [
                            {"code": "create"},
                            {"code": "read"},
                            {"code": "search-type"},
                        ],
                    }
                ],
            }
        ],
    }


@dataclass
class StoredTask:
    resource: dict[str, Any]
    received_at: str


class TaskStore:
    def __init__(self):
        self._lock = Lock()
        self._tasks: dict[str, StoredTask] = {}
        self._order: list[str] = []

    def save(self, task: dict[str, Any]) -> StoredTask:
        task_id = str(task.get("id") or "").strip()
        if not task_id:
            raise ValueError("Task.id ontbreekt")
        stored = StoredTask(resource=copy.deepcopy(task), received_at=_now_iso())
        with self._lock:
            if task_id not in self._tasks:
                self._order.append(task_id)
            self._tasks[task_id] = stored
        return stored

    def get(self, task_id: str) -> Optional[StoredTask]:
        with self._lock:
            stored = self._tasks.get(task_id)
            if stored is None:
                return None
            return StoredTask(resource=copy.deepcopy(stored.resource), received_at=stored.received_at)

    def list(self) -> list[StoredTask]:
        with self._lock:
            return [
                StoredTask(resource=copy.deepcopy(self._tasks[task_id].resource), received_at=self._tasks[task_id].received_at)
                for task_id in self._order
                if task_id in self._tasks
            ]

    def latest(self) -> Optional[StoredTask]:
        with self._lock:
            if not self._order:
                return None
            task_id = self._order[-1]
            stored = self._tasks.get(task_id)
            if stored is None:
                return None
            return StoredTask(resource=copy.deepcopy(stored.resource), received_at=stored.received_at)

    def clear(self) -> int:
        with self._lock:
            count = len(self._tasks)
            self._tasks.clear()
            self._order.clear()
            return count


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient()
    try:
        yield
    finally:
        await app.state.http_client.aclose()


app = FastAPI(title="Mock Notification Receiver", lifespan=lifespan)
app.state.task_store = TaskStore()


@app.get("/health")
async def health() -> dict[str, Any]:
    tasks = app.state.task_store.list()
    return {
        "ok": True,
        "service": "mock-notification-receiver",
        "public_base": settings.public_base,
        "require_bearer_token": bool(settings.require_bearer_token),
        "required_scope": str(settings.required_scope or "").strip() or None,
        "stored_tasks": len(tasks),
    }


@app.get("/fhir/metadata")
async def metadata() -> Response:
    return _fhir_json_response(_capability_statement())


@app.get("/fhir/Task")
async def list_tasks() -> Response:
    entries = []
    for stored in app.state.task_store.list():
        entries.append(
            {
                "resource": stored.resource,
            }
        )
    bundle = {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(entries),
        "entry": entries,
    }
    return _fhir_json_response(bundle)


@app.post("/fhir/Task")
async def create_task(payload: dict[str, Any], request: Request) -> Response:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="FHIR Task body moet een JSON object zijn.")
    resource_type = str(payload.get("resourceType") or "").strip()
    if resource_type and resource_type != "Task":
        raise HTTPException(status_code=400, detail="Alleen FHIR Task resources zijn toegestaan.")

    task = copy.deepcopy(payload)
    task["resourceType"] = "Task"
    await _authorize_notification_request(request, task)
    task_id = str(task.get("id") or "").strip() or str(uuid.uuid4())
    task["id"] = task_id
    if not str(task.get("status") or "").strip():
        task["status"] = settings.default_task_status

    meta = task.get("meta")
    if not isinstance(meta, dict):
        meta = {}
    meta["lastUpdated"] = _now_iso()
    task["meta"] = meta

    stored = app.state.task_store.save(task)
    headers = {
        "Location": f"{str(settings.public_base or '').rstrip('/')}/Task/{task_id}",
        "Content-Location": f"{str(settings.public_base or '').rstrip('/')}/Task/{task_id}",
    }
    return _fhir_json_response(stored.resource, status_code=201, headers=headers)


@app.get("/fhir/Task/{task_id}")
async def read_task(task_id: str) -> Response:
    stored = app.state.task_store.get(task_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Task niet gevonden.")
    return _fhir_json_response(stored.resource)


@app.get("/debug/tasks")
async def debug_tasks() -> dict[str, Any]:
    tasks = app.state.task_store.list()
    return {
        "total": len(tasks),
        "tasks": [
            {
                "received_at": stored.received_at,
                "summary": _task_summary(stored.resource, received_at=stored.received_at),
                "resource": stored.resource,
            }
            for stored in tasks
        ],
    }


@app.get("/debug/tasks/latest")
async def debug_latest_task() -> dict[str, Any]:
    stored = app.state.task_store.latest()
    if stored is None:
        raise HTTPException(status_code=404, detail="Nog geen Task ontvangen.")
    return {
        "received_at": stored.received_at,
        "summary": _task_summary(stored.resource, received_at=stored.received_at),
        "resource": stored.resource,
    }


@app.get("/debug/tasks/latest-summary")
async def debug_latest_summary() -> dict[str, Any]:
    stored = app.state.task_store.latest()
    if stored is None:
        raise HTTPException(status_code=404, detail="Nog geen Task ontvangen.")
    return _task_summary(stored.resource, received_at=stored.received_at)


@app.delete("/debug/tasks")
async def reset_tasks() -> dict[str, Any]:
    deleted = app.state.task_store.clear()
    return {"ok": True, "deleted": deleted}


if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=False)
