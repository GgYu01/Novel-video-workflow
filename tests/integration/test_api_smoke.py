from __future__ import annotations

from fastapi.testclient import TestClient

from av_workflow.api.app import create_app


def test_api_smoke_job_lifecycle_and_artifact_summary() -> None:
    client = TestClient(create_app())

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    created = client.post(
        "/v1/jobs",
        json={
            "input_mode": "upload",
            "source_ref": "asset://source.txt",
            "output_preset": "short-story",
            "profile_id": "internal-prod",
            "language": "zh-CN",
            "review_level": "strict",
        },
    )
    assert created.status_code == 201
    job_payload = created.json()

    job_id = job_payload["job_id"]
    assert job_payload["status"] == "created"

    fetched = client.get(f"/v1/jobs/{job_id}")
    assert fetched.status_code == 200
    assert fetched.json()["job_id"] == job_id

    artifacts = client.get(f"/v1/jobs/{job_id}/artifacts")
    assert artifacts.status_code == 200
    assert artifacts.json() == {
        "job_id": job_id,
        "final_video_ref": None,
        "subtitle_refs": [],
        "preview_refs": [],
        "cover_refs": [],
    }
