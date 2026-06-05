from pathlib import Path

from fastapi.testclient import TestClient

from minixd.app import create_app


def test_project_create_list_get_and_persist_with_data_dir(tmp_path: Path) -> None:
    client = TestClient(create_app(mock=True, data_dir=tmp_path))
    document = _document("doc_project")

    created_response = client.post(
        "/v1/projects",
        json={
            "name": "Kitchen checklist",
            "document": document,
        },
    )

    assert created_response.status_code == 201
    created = created_response.json()
    assert created["projectId"].startswith("prj_")
    assert created["name"] == "Kitchen checklist"
    assert created["document"] == document
    assert created["createdAt"] == created["updatedAt"]
    assert "assets" not in created

    list_response = client.get("/v1/projects")
    assert list_response.status_code == 200
    assert list_response.json() == {
        "projects": [
            {
                "projectId": created["projectId"],
                "name": "Kitchen checklist",
                "documentId": "doc_project",
                "updatedAt": created["updatedAt"],
            }
        ]
    }

    get_response = client.get(f"/v1/projects/{created['projectId']}")
    assert get_response.status_code == 200
    assert get_response.json()["document"] == document

    restarted = TestClient(create_app(mock=True, data_dir=tmp_path))

    persisted_response = restarted.get(f"/v1/projects/{created['projectId']}")
    assert persisted_response.status_code == 200
    assert persisted_response.json()["document"] == document
    assert restarted.get("/v1/projects").json()["projects"][0]["projectId"] == created["projectId"]


def test_project_update_and_delete_persist_with_data_dir(tmp_path: Path) -> None:
    client = TestClient(create_app(mock=True, data_dir=tmp_path))
    created = client.post(
        "/v1/projects",
        json={"name": "Draft", "document": _document("doc_draft")},
    ).json()
    updated_document = _document("doc_updated")
    updated_document["title"] = "Updated project"

    update_response = client.put(
        f"/v1/projects/{created['projectId']}",
        json={"name": "Updated checklist", "document": updated_document},
    )

    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["projectId"] == created["projectId"]
    assert updated["name"] == "Updated checklist"
    assert updated["document"] == updated_document
    assert updated["createdAt"] == created["createdAt"]

    restarted = TestClient(create_app(mock=True, data_dir=tmp_path))
    persisted = restarted.get(f"/v1/projects/{created['projectId']}").json()
    assert persisted["name"] == "Updated checklist"
    assert persisted["document"]["id"] == "doc_updated"

    delete_response = restarted.delete(f"/v1/projects/{created['projectId']}")

    assert delete_response.status_code == 204
    assert restarted.get(f"/v1/projects/{created['projectId']}").status_code == 404
    assert restarted.get("/v1/projects").json() == {"projects": []}
    assert not (tmp_path / "projects" / created["projectId"]).exists()


def _document(document_id: str) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "id": document_id,
        "title": "Project fixture",
        "target": {
            "profileId": "seznik-minix-s1-lyin48d-gy",
            "widthDots": 384,
            "heightDots": 120,
            "dpi": 203,
            "paperMode": "continuous",
            "density": "medium",
        },
        "background": {"color": "#ffffff"},
        "elements": [],
        "assets": [],
        "metadata": {},
    }
