import importlib.util
import sys
from pathlib import Path

from fastapi.testclient import TestClient


def _import_app_module():
    module_name = "mock_notification_receiver_main_test"
    sys.modules.pop(module_name, None)
    sys.modules.pop("configs", None)
    service_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(service_root))
    module_path = service_root / "main.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    try:
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    finally:
        if sys.path and sys.path[0] == str(service_root):
            sys.path.pop(0)
    return module


def _set_settings(monkeypatch, appmod) -> None:
    monkeypatch.setattr(appmod.settings, "public_base", "https://mach2.disyepd.com/receiver-mock/fhir", raising=False)
    monkeypatch.setattr(appmod.settings, "default_task_status", "requested", raising=False)
    monkeypatch.setattr(appmod.settings, "require_bearer_token", True, raising=False)
    monkeypatch.setattr(appmod.settings, "required_scope", "eOverdracht-receiver", raising=False)


def _task_payload(sender_ura: str = "12345678") -> dict:
    return {
        "resourceType": "Task",
        "status": "requested",
        "basedOn": [{"reference": "Task/wf-123"}],
        "requester": {
            "onBehalfOf": {
                "identifier": {
                    "system": "http://fhir.nl/fhir/NamingSystem/ura",
                    "value": sender_ura,
                }
            }
        },
        "owner": {
            "identifier": {
                "system": "http://fhir.nl/fhir/NamingSystem/ura",
                "value": "87654321",
            }
        },
        "for": {
            "identifier": {
                "system": "http://fhir.nl/fhir/NamingSystem/bsn",
                "value": "999999990",
            }
        },
        "input": [
            {
                "type": {
                    "coding": [
                        {
                            "system": "http://fhir.nl/fhir/NamingSystem/TaskParameter",
                            "code": "authorization-base",
                        }
                    ]
                },
                "valueString": "auth-123",
            }
        ],
        "extension": [
            {
                "url": "http://example.org/fhir/StructureDefinition/sender-bgz-base",
                "valueUrl": "https://mach2.disyepd.com/notifiedpull/fhir",
            }
        ],
    }


def test_metadata_advertises_task_create(monkeypatch):
    appmod = _import_app_module()
    _set_settings(monkeypatch, appmod)
    with TestClient(appmod.app) as client:
        response = client.get("/fhir/metadata")
    assert response.status_code == 200
    body = response.json()
    assert body["resourceType"] == "CapabilityStatement"
    interactions = body["rest"][0]["resource"][0]["interaction"]
    assert any(item["code"] == "create" for item in interactions)


def test_post_task_requires_bearer_token(monkeypatch):
    appmod = _import_app_module()
    _set_settings(monkeypatch, appmod)

    with TestClient(appmod.app) as client:
        response = client.post("/fhir/Task", json=_task_payload())

    assert response.status_code == 401
    assert response.json()["detail"]["reason"] == "missing_bearer_token"


def test_post_task_is_stored_and_summarized(monkeypatch):
    appmod = _import_app_module()
    _set_settings(monkeypatch, appmod)

    async def _fake_introspect(_token: str):
        return appmod.TokenContext(
            raw={},
            active=True,
            organization_ura="12345678",
            scopes=["eOverdracht-receiver"],
        )

    monkeypatch.setattr(appmod, "_introspect_token", _fake_introspect)

    with TestClient(appmod.app) as client:
        reset = client.delete("/debug/tasks")
        assert reset.status_code == 200

        response = client.post(
            "/fhir/Task",
            json=_task_payload(),
            headers={"Authorization": "Bearer test-token"},
        )

        assert response.status_code == 201, response.text
        created = response.json()
        assert created["id"]
        assert response.headers["Location"].endswith(f"/Task/{created['id']}")

        latest = client.get("/debug/tasks/latest-summary")
        assert latest.status_code == 200
        summary = latest.json()
        assert summary["based_on"] == "Task/wf-123"
        assert summary["authorization_base"] == "auth-123"
        assert summary["sender_bgz_base"] == "https://mach2.disyepd.com/notifiedpull/fhir"
        assert summary["owner_ura"] == "87654321"
        assert summary["patient_bsn"] == "999999990"
        assert summary["sender_ura"] == "12345678"

        task_read = client.get(f"/fhir/Task/{created['id']}")
        assert task_read.status_code == 200
        assert task_read.json()["id"] == created["id"]

        task_search = client.get("/fhir/Task")
        assert task_search.status_code == 200
        bundle = task_search.json()
        assert bundle["resourceType"] == "Bundle"
        assert bundle["total"] == 1


def test_post_task_rejects_when_token_organization_does_not_match_task(monkeypatch):
    appmod = _import_app_module()
    _set_settings(monkeypatch, appmod)

    async def _fake_introspect(_token: str):
        return appmod.TokenContext(
            raw={},
            active=True,
            organization_ura="99999999",
            scopes=["eOverdracht-receiver"],
        )

    monkeypatch.setattr(appmod, "_introspect_token", _fake_introspect)

    with TestClient(appmod.app) as client:
        response = client.post(
            "/fhir/Task",
            json=_task_payload(sender_ura="12345678"),
            headers={"Authorization": "Bearer test-token"},
        )

    assert response.status_code == 403
    assert response.json()["detail"]["reason"] == "organization_not_authorized"
