from __future__ import annotations

import subprocess
from pathlib import Path

from av_workflow.runtime.ffmpeg import SubprocessFfmpegExecutor


def test_subprocess_ffmpeg_executor_prefixes_binary_and_prepares_output_directory(
    tmp_path: Path, monkeypatch
) -> None:
    calls: list[tuple[list[str], bool, str | None]] = []

    def fake_run(command, check, cwd=None):  # type: ignore[no-untyped-def]
        calls.append((command, check, cwd))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    executor = SubprocessFfmpegExecutor(binary="ffmpeg")
    output_path = tmp_path / "nested" / "clip.mp4"

    executor.run(["-version"], cwd=tmp_path, output_path=output_path)

    assert calls == [(["ffmpeg", "-version"], True, str(tmp_path))]
    assert output_path.parent.is_dir()
