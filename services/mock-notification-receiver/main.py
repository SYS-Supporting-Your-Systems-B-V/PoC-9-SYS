from __future__ import annotations

import copy
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Response
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


app = FastAPI(title="Mock Notification Receiver")
app.state.task_store = TaskStore()


@app.get("/health")
async def health() -> dict[str, Any]:
    tasks = app.state.task_store.list()
    return {
        "ok": True,
        "service": "mock-notification-receiver",
        "public_base": settings.public_base,
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
async def create_task(payload: dict[str, Any]) -> Response:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="FHIR Task body moet een JSON object zijn.")
    resource_type = str(payload.get("resourceType") or "").strip()
    if resource_type and resource_type != "Task":
        raise HTTPException(status_code=400, detail="Alleen FHIR Task resources zijn toegestaan.")

    task = copy.deepcopy(payload)
    task["resourceType"] = "Task"
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
