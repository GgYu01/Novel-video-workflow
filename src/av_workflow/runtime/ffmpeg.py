from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Protocol


class FfmpegExecutor(Protocol):
    def run(self, args: list[str], *, cwd: Path | None = None, output_path: Path) -> None:
        """Run an ffmpeg command for a known output path."""


class SubprocessFfmpegExecutor:
    def __init__(self, binary: str = "ffmpeg") -> None:
        self.binary = binary

    def run(self, args: list[str], *, cwd: Path | None = None, output_path: Path) -> None:
        command = [self.binary, *args]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(command, check=True, cwd=str(cwd) if cwd is not None else None)
