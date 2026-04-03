from __future__ import annotations

from fastapi.testclient import TestClient

from av_workflow.api.app import create_app


def test_hybrid_job_flow_exposes_stage_and_shot_artifacts() -> None:
    client = TestClient(create_app())

    created = client.post(
        "/v1/jobs",
        json={
            "input_mode": "upload",
            "source_ref": "asset://source.txt",
            "output_preset": "preview_720p24",
            "profile_id": "internal-prod",
            "language": "zh-CN",
            "review_level": "strict",
        },
    )
    job_id = created.json()["job_id"]

    stage_updated = client.patch(
        f"/v1/jobs/{job_id}/stage",
        json={
            "status": "audio_ready",
            "current_stage": "audio_ready",
        },
    )
    assert stage_updated.status_code == 200

    artifacts_updated = client.patch(
        f"/v1/jobs/{job_id}/artifacts",
        json={
            "subtitle_refs": ["asset://subtitles/final.srt"],
            "audio_refs": [
                "asset://audio/narration.wav",
                "asset://audio/dialogue.wav",
            ],
            "primary_audio_ref": "asset://audio/final-mix.wav",
            "preview_refs": ["asset://preview/final.png"],
            "cover_refs": ["asset://cover/final.png"],
            "final_video_ref": "asset://video/final.mp4",
        },
    )
    assert artifacts_updated.status_code == 200

    shot_updated = client.patch(
        f"/v1/jobs/{job_id}/shots/shot-001/artifacts",
        json={
            "clip_ref": "asset://shots/shot-001.mp4",
            "frame_refs": ["asset://shots/shot-001/frame-001.png"],
        },
    )
    assert shot_updated.status_code == 200

    stage = client.get(f"/v1/jobs/{job_id}/stage")
    assert stage.status_code == 200
    assert stage.json() == {
        "job_id": job_id,
        "status": "audio_ready",
        "current_stage": "audio_ready",
        "retry_count": 0,
        "max_auto_retries": 2,
    }

    artifacts = client.get(f"/v1/jobs/{job_id}/artifacts")
    assert artifacts.status_code == 200
    assert artifacts.json()["primary_audio_ref"] == "asset://audio/final-mix.wav"
    assert artifacts.json()["final_video_ref"] == "asset://video/final.mp4"
    assert artifacts.json()["subtitle_refs"] == ["asset://subtitles/final.srt"]

    shot_artifacts = client.get(f"/v1/jobs/{job_id}/shots/shot-001/artifacts")
    assert shot_artifacts.status_code == 200
    assert shot_artifacts.json() == {
        "job_id": job_id,
        "shot_id": "shot-001",
        "clip_ref": "asset://shots/shot-001.mp4",
        "frame_refs": ["asset://shots/shot-001/frame-001.png"],
    }
