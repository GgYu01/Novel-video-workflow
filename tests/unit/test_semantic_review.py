from __future__ import annotations

from pathlib import Path
import textwrap

from av_workflow.contracts.enums import ReviewMode, ReviewResult, ShotType
from av_workflow.contracts.models import AssetManifest, Job, ShotPlan, ShotPlanSet
from av_workflow.services.compose import build_asset_manifest
from av_workflow.services.review.semantic import (
    FailClosedSemanticReviewService,
    LlamaCppCliSemanticReviewService,
)


def build_job() -> Job:
    return Job(
        job_id="job-001",
        input_mode="upload",
        source_ref="asset://source.txt",
        output_preset="preview_720p24",
        profile_id="internal-prod",
        language="zh-CN",
        review_level="strict",
    )


def build_shot_plan_set(*, shot_ids: tuple[str, ...] = ("shot-001",)) -> ShotPlanSet:
    shots: list[ShotPlan] = []
    for index, shot_id in enumerate(shot_ids, start=1):
        shots.append(
            ShotPlan(
                shot_id=shot_id,
                chapter_id="ch-1",
                scene_id=f"scene-{index}",
                duration_target=4.0,
                shot_type=ShotType.MEDIUM,
                camera_instruction=f"steady eye-level framing {index}",
                subject_instruction=f"Subject {index} remains visually consistent",
                environment_instruction=f"Environment {index} stays coherent",
                narration_text=f"Narration for shot {index}.",
                dialogue_lines=[],
                subtitle_source="narration",
                render_requirements={"aspect_ratio": "16:9"},
                review_targets={"must_match": [f"subject-{index}", f"scene-{index}"]},
                fallback_strategy={"retry_scope": "shot"},
            )
        )
    return ShotPlanSet(
        shot_plan_set_id="shot-plan-set-001",
        story_id="story-001",
        chapter_id="ch-1",
        default_output_preset="preview_720p24",
        shots=shots,
        version=1,
    )


def build_manifest() -> AssetManifest:
    return build_asset_manifest(
        job=build_job(),
        shot_plans=build_shot_plan_set().shots,
        rendered_shots={
            "shot-001": {
                "clip_ref": "asset://runtime/jobs/job-001/shots/shot-001/render/clip.mp4",
                "frame_refs": ["asset://runtime/jobs/job-001/shots/shot-001/render/frame-001.png"],
                "render_metadata": {"content_source": "image_model"},
            }
        },
        subtitle_refs=["asset://runtime/jobs/job-001/subtitles/shot-001.srt"],
        audio_refs=["asset://runtime/jobs/job-001/audio/final-mix.wav"],
        audio_mix_ref="asset://runtime/jobs/job-001/audio/final-mix.wav",
        preview_refs=["asset://runtime/jobs/job-001/output/preview.png"],
        cover_refs=["asset://runtime/jobs/job-001/output/cover.png"],
        final_video_ref="asset://runtime/jobs/job-001/output/final.mp4",
    )


def build_quality_cli(tmp_path: Path) -> tuple[Path, Path]:
    args_log = tmp_path / "cli-args.txt"
    cli_path = tmp_path / "fake-llama-mtmd-cli.sh"
    cli_path.write_text(
        textwrap.dedent(
            f"""\
            #!/bin/sh
            set -eu
            printf '%s\\n' "$@" > "{args_log}"
            contains_low_info=0
            contains_rich=0
            prev=""
            for arg in "$@"; do
              if [ "$prev" = "--image" ]; then
                case "$arg" in
                  *low-info*) contains_low_info=1 ;;
                  *rich*) contains_rich=1 ;;
                esac
              fi
              prev="$arg"
            done
            echo "warming up reviewer"
            if [ "$contains_low_info" -eq 1 ]; then
              echo '{{"result":"fail","score":0.18,"reason_codes":["low_visual_density","continuity_risk"],"reason_text":"Frame is too sparse for a reliable review.","recommended_action":"manual_hold","fix_hint":"Regenerate a denser frame before delivery.","latency_ms":214}}'
            elif [ "$contains_rich" -eq 1 ]; then
              echo '{{"result":"pass","score":0.96,"reason_codes":["character_match","scene_match"],"reason_text":"The frame matches the requested scene.","recommended_action":"continue","fix_hint":null,"latency_ms":214}}'
            else
              echo '{{"result":"warn","score":0.6,"reason_codes":["uncertain_visual_match"],"reason_text":"The frame is usable but not strongly grounded.","recommended_action":"manual_hold","fix_hint":"Use a clearer generated frame.","latency_ms":214}}'
            fi
            """
        ),
        encoding="utf-8",
    )
    cli_path.chmod(0o755)
    return cli_path, args_log


def test_fail_closed_semantic_review_service_returns_manual_hold_review() -> None:
    service = FailClosedSemanticReviewService(
        reason_code="semantic_review_backend_disabled",
        reason_text="Semantic review backend is disabled.",
        fix_hint="Enable a semantic image-review backend before auto-completion.",
    )

    review = service.evaluate(
        job=build_job(),
        manifest=build_manifest(),
        shot_plan_set=build_shot_plan_set(),
        frame_path_map=None,
    )

    assert review.review_mode is ReviewMode.SEMANTIC_IMAGE
    assert review.result is ReviewResult.FAIL
    assert review.recommended_action == "manual_hold"
    assert review.reason_codes == ["semantic_review_backend_disabled"]


def test_llama_cpp_cli_semantic_review_service_samples_multiple_frames_and_uses_prompt_ref(
    tmp_path: Path,
) -> None:
    frame_paths = [tmp_path / f"frame-{index:03d}.png" for index in range(1, 6)]
    for frame_path in frame_paths:
        frame_path.write_bytes(b"fake-png")
    args_log = tmp_path / "cli-args.txt"
    cli_path = tmp_path / "fake-llama-mtmd-cli.sh"
    cli_path.write_text(
        "\n".join(
            [
                "#!/bin/sh",
                f"printf '%s\\n' \"$@\" > {args_log}",
                "echo 'warming up reviewer'",
                "echo '{\"result\":\"pass\",\"score\":0.94,\"reason_codes\":[\"character_match\"],\"reason_text\":\"Shot matches the requested scene.\",\"recommended_action\":\"continue\",\"fix_hint\":null,\"latency_ms\":321}'",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    cli_path.chmod(0o755)

    service = LlamaCppCliSemanticReviewService(
        command_path=str(cli_path),
        model_path="/models/review/Qwen3-VL-8B-Instruct-Q8_0.gguf",
        mmproj_path="/models/review/Qwen3-VL-8B-Instruct-mmproj-Q8_0.gguf",
        timeout_sec=30.0,
        max_tokens=256,
        ctx_size=4096,
        max_input_frames=3,
        extra_args=("--temp", "0.0", "--top-p", "1.0"),
        prompt_ref="prompt://review/semantic-custom",
    )

    review = service.evaluate(
        job=build_job(),
        manifest=build_manifest(),
        shot_plan_set=build_shot_plan_set(),
        frame_path_map={"shot-001": frame_paths},
    )

    args = args_log.read_text(encoding="utf-8").splitlines()

    assert review.result is ReviewResult.PASS
    assert review.recommended_action == "continue"
    assert review.review_mode is ReviewMode.SEMANTIC_IMAGE
    assert review.evaluation_prompt_ref == "prompt://review/semantic-custom"
    assert review.input_assets == [
        str(frame_paths[0]),
        str(frame_paths[2]),
        str(frame_paths[4]),
    ]
    assert "--model" in args
    assert "/models/review/Qwen3-VL-32B-Instruct-Q4_K_M.gguf" in args
    assert "--mmproj" in args
    assert "/models/review/Qwen3-VL-32B-Instruct-mmproj-Q8_0.gguf" in args
    assert args.count("--image") == 3
    assert str(frame_paths[0]) in args
    assert str(frame_paths[2]) in args
    assert str(frame_paths[4]) in args
    assert str(frame_paths[1]) not in args
    assert str(frame_paths[3]) not in args
    assert "--temp" in args
    assert "0.0" in args
    assert "--top-p" in args
    assert "1.0" in args
    assert "-p" in args


def test_llama_cpp_cli_semantic_review_service_flags_low_information_frames(tmp_path: Path) -> None:
    frame_paths = [
        tmp_path / "frame-001-low-info.png",
        tmp_path / "frame-002-rich.png",
        tmp_path / "frame-003-rich.png",
    ]
    for frame_path in frame_paths:
        frame_path.write_bytes(b"fake-png")

    cli_path, args_log = build_quality_cli(tmp_path)

    service = LlamaCppCliSemanticReviewService(
        command_path=str(cli_path),
        model_path="/models/review/Qwen3-VL-8B-Instruct-Q8_0.gguf",
        mmproj_path="/models/review/Qwen3-VL-8B-Instruct-mmproj-Q8_0.gguf",
        timeout_sec=30.0,
        max_tokens=256,
        ctx_size=4096,
        max_input_frames=3,
        extra_args=("--temp", "0.0", "--top-p", "1.0"),
    )

    review = service.evaluate(
        job=build_job(),
        manifest=build_manifest(),
        shot_plan_set=build_shot_plan_set(),
        frame_path_map={"shot-001": frame_paths},
    )

    args = args_log.read_text(encoding="utf-8").splitlines()

    assert review.review_mode is ReviewMode.SEMANTIC_IMAGE
    assert review.result is ReviewResult.FAIL
    assert review.recommended_action == "manual_hold"
    assert set(review.reason_codes) == {"low_visual_density", "continuity_risk"}
    assert review.input_assets == [str(path) for path in frame_paths]
    assert args.count("--image") == 3
    assert str(frame_paths[0]) in args
    assert str(frame_paths[1]) in args
    assert str(frame_paths[2]) in args


def test_llama_cpp_cli_semantic_review_service_launches_once_per_job_by_default(
    tmp_path: Path,
) -> None:
    shot_plan_set = build_shot_plan_set(shot_ids=("shot-001", "shot-002"))
    first_shot_frames = [tmp_path / f"shot-001-frame-{index:03d}.png" for index in range(1, 5)]
    second_shot_frames = [tmp_path / f"shot-002-frame-{index:03d}.png" for index in range(1, 4)]
    for frame_path in [*first_shot_frames, *second_shot_frames]:
        frame_path.write_bytes(b"fake-png")

    invocation_log = tmp_path / "cli-invocations.txt"
    args_log = tmp_path / "cli-args.txt"
    cli_path = tmp_path / "fake-llama-mtmd-cli.sh"
    cli_path.write_text(
        "\n".join(
            [
                "#!/bin/sh",
                f"echo run >> {invocation_log}",
                f"printf '%s\\n' \"$@\" > {args_log}",
                "echo '{\"result\":\"pass\",\"score\":0.93,\"reason_codes\":[\"job_semantic_alignment_ok\"],\"reason_text\":\"The sampled frames remain coherent across the job.\",\"recommended_action\":\"continue\",\"fix_hint\":null,\"latency_ms\":222}'",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    cli_path.chmod(0o755)

    service = LlamaCppCliSemanticReviewService(
        command_path=str(cli_path),
        model_path="/models/review/Qwen3-VL-8B-Instruct-Q8_0.gguf",
        mmproj_path="/models/review/Qwen3-VL-8B-Instruct-mmproj-Q8_0.gguf",
        timeout_sec=30.0,
        max_tokens=256,
        ctx_size=4096,
        max_input_frames=2,
    )

    review = service.evaluate(
        job=build_job(),
        manifest=build_manifest(),
        shot_plan_set=shot_plan_set,
        frame_path_map={
            "shot-001": first_shot_frames,
            "shot-002": second_shot_frames,
        },
    )

    args = args_log.read_text(encoding="utf-8").splitlines()
    invocation_count = len(invocation_log.read_text(encoding="utf-8").splitlines())
    expected_selected_frames = [
        str(first_shot_frames[0]),
        str(first_shot_frames[-1]),
        str(second_shot_frames[0]),
        str(second_shot_frames[-1]),
    ]

    assert invocation_count == 1
    assert review.result is ReviewResult.PASS
    assert review.input_assets == expected_selected_frames
    assert args.count("--image") == len(expected_selected_frames)
    for frame_path in expected_selected_frames:
        assert frame_path in args
    prompt = "\n".join(args[args.index("-p") + 1 :])
    assert "Shots: 2" in prompt
    assert "Shot shot-001" in prompt
    assert "Shot shot-002" in prompt


def test_llama_cpp_cli_semantic_review_service_accepts_visually_rich_frame(tmp_path: Path) -> None:
    rich_frame = tmp_path / "shot-001-rich.png"
    rich_frame.write_bytes(b"fake-rich")
    cli_path, _ = build_quality_cli(tmp_path)

    service = LlamaCppCliSemanticReviewService(
        command_path=str(cli_path),
        model_path="/models/review/Qwen3-VL-8B-Instruct-Q8_0.gguf",
        mmproj_path="/models/review/Qwen3-VL-8B-Instruct-mmproj-Q8_0.gguf",
        timeout_sec=30.0,
        max_tokens=256,
        ctx_size=4096,
        max_input_frames=4,
    )

    review = service.evaluate(
        job=build_job(),
        manifest=build_manifest(),
        shot_plan_set=build_shot_plan_set(),
        frame_path_map={"shot-001": [rich_frame]},
    )

    assert review.review_mode is ReviewMode.SEMANTIC_IMAGE
    assert review.result is ReviewResult.PASS
    assert review.recommended_action == "continue"
    assert "character_match" in review.reason_codes
