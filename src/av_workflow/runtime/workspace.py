from __future__ import annotations

import json
from pathlib import Path


class RuntimeWorkspace:
    def __init__(self, *, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir)

    def job_root(self, job_id: str) -> Path:
        return self.root_dir / "jobs" / job_id

    def shot_root(self, job_id: str, shot_id: str) -> Path:
        return self.job_root(job_id) / "shots" / shot_id

    def planning_dir(self, job_id: str) -> Path:
        return self.job_root(job_id) / "planning"

    def audio_dir(self, job_id: str) -> Path:
        return self.job_root(job_id) / "audio"

    def compose_dir(self, job_id: str) -> Path:
        return self.job_root(job_id) / "compose"

    def output_dir(self, job_id: str) -> Path:
        return self.job_root(job_id) / "output"

    def ensure_job_tree(self, job_id: str) -> Path:
        job_root = self.job_root(job_id)
        for path in (
            job_root,
            self.planning_dir(job_id),
            self.audio_dir(job_id),
            self.compose_dir(job_id),
            self.output_dir(job_id),
            job_root / "shots",
        ):
            path.mkdir(parents=True, exist_ok=True)
        return job_root

    def write_text_artifact(self, job_id: str, relative_path: str, text: str) -> Path:
        target = self.job_root(job_id) / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target

    def write_json_artifact(self, job_id: str, relative_path: str, payload: object) -> Path:
        return self.write_text_artifact(
            job_id,
            relative_path,
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        )

    def asset_ref(self, job_id: str, *parts: str) -> str:
        suffix = "/".join(part.strip("/") for part in parts if part)
        if suffix:
            return f"asset://runtime/jobs/{job_id}/{suffix}"
        return f"asset://runtime/jobs/{job_id}"
