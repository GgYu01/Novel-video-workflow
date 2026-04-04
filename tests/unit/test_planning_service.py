from __future__ import annotations

from av_workflow.contracts.enums import MotionTier, ShotType
from av_workflow.contracts.models import ShotPlanSet, SourceDocument
from av_workflow.services.planning import DeterministicPlanningService, HeuristicChapterShotPlanner


class StubShotPlanner:
    def __init__(self) -> None:
        self.calls: list[tuple[SourceDocument, str]] = []

    def build_shots(self, source_document: SourceDocument, story_id: str) -> list[dict[str, object]]:
        self.calls.append((source_document, story_id))
        first_chapter = source_document.chapter_documents[0]
        return [
            {
                "shot_id": "shot-001",
                "chapter_id": first_chapter["chapter_id"],
                "scene_id": "scene-001",
                "duration_target": 4.0,
                "shot_type": ShotType.MEDIUM,
                "camera_instruction": "steady eye-level framing",
                "subject_instruction": "crowd throws the coach into the air in celebration",
                "environment_instruction": "Saint Moix Stadium packed with cheering supporters",
                "narration_text": "The celebration exploded across the stadium.",
                "dialogue_lines": [],
                "subtitle_source": "narration",
                "render_requirements": {"aspect_ratio": "16:9"},
                "review_targets": {"must_match": ["traveler", "station"]},
                "fallback_strategy": {"retry_scope": "shot"},
            }
        ]


def build_source_document() -> SourceDocument:
    return SourceDocument(
        source_document_id="source-001",
        job_id="job-001",
        source_ref="asset://source.txt",
        title="Arrival",
        language="zh-CN",
        normalized_text=(
            "Chapter 1: Arrival at Saint Moix Stadium\n"
            "Jose Alemany watched Antonio Asensio celebrate at Saint Moix Stadium.\n"
            "Jose Alemany promised Mateo Alemany he would rebuild Mallorca."
        ),
        chapter_documents=[
            {
                "chapter_id": "ch-1",
                "title": "Chapter 1: Arrival at Saint Moix Stadium",
                "content": (
                    "Jose Alemany watched Antonio Asensio celebrate at Saint Moix Stadium. "
                    "Jose Alemany promised Mateo Alemany he would rebuild Mallorca."
                ),
            }
        ],
    )


def test_planning_service_builds_story_spec_from_source_document() -> None:
    service = DeterministicPlanningService(shot_planner=StubShotPlanner())
    source = build_source_document()

    story_spec = service.build_story_spec(source)

    assert story_spec.story_id == source.source_document_id
    assert story_spec.approved_for_planning is True
    assert story_spec.spec_validation_result == "validated"
    assert story_spec.chapter_specs[0]["chapter_id"] == "ch-1"
    assert any(
        character["canonical_name"] == "Jose Alemany"
        for character in story_spec.character_registry
    )
    assert any(
        location["location_name"] == "Saint Moix Stadium"
        for location in story_spec.location_registry
    )


def test_planning_service_generates_shot_plans_via_injected_planner() -> None:
    planner = StubShotPlanner()
    service = DeterministicPlanningService(shot_planner=planner)
    source = build_source_document()
    story_spec = service.build_story_spec(source)

    shot_plans = service.generate_shot_plans(source, story_spec)

    assert len(shot_plans) == 1
    assert shot_plans[0].shot_type is ShotType.MEDIUM
    assert shot_plans[0].motion_tier is MotionTier.WAN_DYNAMIC
    assert planner.calls == [(source, story_spec.story_id)]


def test_planning_service_groups_shots_into_shot_plan_set() -> None:
    planner = StubShotPlanner()
    service = DeterministicPlanningService(shot_planner=planner)
    source = build_source_document()
    story_spec = service.build_story_spec(source)

    shot_plan_set = service.generate_shot_plan_set(
        source_document=source,
        story_spec=story_spec,
        output_preset="preview_720p24",
    )

    assert isinstance(shot_plan_set, ShotPlanSet)
    assert shot_plan_set.chapter_id == "ch-1"
    assert shot_plan_set.default_output_preset == "preview_720p24"
    assert shot_plan_set.shots[0].motion_tier is MotionTier.WAN_DYNAMIC


def test_heuristic_planner_marks_chinese_action_segments_as_wan_dynamic() -> None:
    service = DeterministicPlanningService(shot_planner=HeuristicChapterShotPlanner())
    source = SourceDocument(
        source_document_id="source-zh-dynamic",
        job_id="job-zh-dynamic",
        source_ref="asset://source-zh.txt",
        title="中文动态片段",
        language="zh-CN",
        normalized_text="球迷在球场看台上欢呼，球员带球冲刺并展开追逐。",
        chapter_documents=[
            {
                "chapter_id": "ch-zh-1",
                "title": "第1章 球场沸腾",
                "content": "球迷在球场看台上欢呼，球员带球冲刺并展开追逐，整个球场陷入疯狂庆祝。",
            }
        ],
    )

    story_spec = service.build_story_spec(source)
    shot_plans = service.generate_shot_plans(source, story_spec)

    assert any(shot.motion_tier is MotionTier.WAN_DYNAMIC for shot in shot_plans)


def test_heuristic_planner_splits_chinese_sentences_without_whitespace() -> None:
    service = DeterministicPlanningService(shot_planner=HeuristicChapterShotPlanner())
    source = SourceDocument(
        source_document_id="source-zh-static",
        job_id="job-zh-static",
        source_ref="asset://source-zh-static.txt",
        title="中文静态片段",
        language="zh-CN",
        normalized_text=(
            "圣·莫伊斯球场的包厢里很安静。"
            "安东尼奥·阿森西奥与马特奥·阿莱马尼坐在窗边，低声商量俱乐部下个赛季的安排。"
            "回到家后，何塞在书桌前整理笔记，慢慢推演马洛卡未来的道路。"
        ),
        chapter_documents=[
            {
                "chapter_id": "ch-zh-static-1",
                "title": "第1章 包厢",
                "content": (
                    "圣·莫伊斯球场的包厢里很安静。"
                    "安东尼奥·阿森西奥与马特奥·阿莱马尼坐在窗边，低声商量俱乐部下个赛季的安排。"
                    "回到家后，何塞在书桌前整理笔记，慢慢推演马洛卡未来的道路。"
                ),
            }
        ],
    )

    story_spec = service.build_story_spec(source)
    shot_plans = service.generate_shot_plans(source, story_spec)

    assert [shot.shot_id for shot in shot_plans] == ["shot-001", "shot-002", "shot-003"]
    assert [shot.narration_text for shot in shot_plans] == [
        "圣·莫伊斯球场的包厢里很安静。",
        "安东尼奥·阿森西奥与马特奥·阿莱马尼坐在窗边，低声商量俱乐部下个赛季的安排。",
        "回到家后，何塞在书桌前整理笔记，慢慢推演马洛卡未来的道路。",
    ]
