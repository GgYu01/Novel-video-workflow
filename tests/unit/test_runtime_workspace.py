from __future__ import annotations

import json
from pathlib import Path

from av_workflow.runtime.workspace import RuntimeWorkspace


def test_runtime_workspace_creates_job_tree_and_artifacts() -> None:
    workspace = RuntimeWorkspace(root_dir=Path("/tmp/runtime-root"))

    job_root = workspace.ensure_job_tree("job-001")

    assert job_root == Path("/tmp/runtime-root/jobs/job-001")
    assert workspace.job_root("job-001") == Path("/tmp/runtime-root/jobs/job-001")
    assert workspace.shot_root("job-001", "shot-001") == Path("/tmp/runtime-root/jobs/job-001/shots/shot-001")

    story_path = workspace.write_text_artifact(
        "job-001",
        "planning/story_spec.json",
        json.dumps({"story_id": "story-001"}),
    )
    manifest_path = workspace.write_json_artifact(
        "job-001",
        "output/output_package.json",
        {"job_id": "job-001", "status": "ready"},
    )

    assert story_path == Path("/tmp/runtime-root/jobs/job-001/planning/story_spec.json")
    assert story_path.read_text(encoding="utf-8") == '{"story_id": "story-001"}'
    assert manifest_path == Path("/tmp/runtime-root/jobs/job-001/output/output_package.json")
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == {
        "job_id": "job-001",
        "status": "ready",
    }


def test_runtime_workspace_builds_asset_refs() -> None:
    workspace = RuntimeWorkspace(root_dir=Path("/tmp/runtime-root"))

    assert workspace.asset_ref("job-001", "shots", "shot-001", "render", "clip.mp4") == (
        "asset://runtime/jobs/job-001/shots/shot-001/render/clip.mp4"
    )
