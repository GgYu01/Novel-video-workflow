from __future__ import annotations

from av_workflow.contracts.models import Job
from av_workflow.services.ingest import normalize_source


def build_job() -> Job:
    return Job(
        job_id="job-001",
        input_mode="upload",
        source_ref="asset://source.txt",
        output_preset="short-story",
        profile_id="internal-prod",
        language="zh-CN",
        review_level="strict",
    )


def test_normalize_source_splits_chapters_from_headings() -> None:
    job = build_job()
    raw_text = """
    Chapter 1: Arrival

    The train arrived at dawn.

    Chapter 2: Crossing
    He crossed the silent station square.
    """

    source = normalize_source(job, raw_text)

    assert source.job_id == job.job_id
    assert source.version == 1
    assert len(source.chapter_documents) == 2
    assert source.chapter_documents[0]["title"] == "Chapter 1: Arrival"
    assert source.chapter_documents[1]["chapter_id"] == "ch-2"
    assert "\n\n\n" not in source.normalized_text


def test_normalize_source_creates_default_chapter_without_headings() -> None:
    job = build_job()
    raw_text = """
    Fog covered the harbor.
    A ferry horn cut through the morning.
    """

    source = normalize_source(job, raw_text)

    assert len(source.chapter_documents) == 1
    assert source.chapter_documents[0]["title"] == "Chapter 1"
    assert source.chapter_documents[0]["content"].startswith("Fog covered the harbor.")


def test_normalize_source_preserves_preface_before_first_heading() -> None:
    job = build_job()
    raw_text = """
    Prologue line.

    Chapter 1: Arrival
    The train arrived at dawn.
    """

    source = normalize_source(job, raw_text)

    assert len(source.chapter_documents) == 1
    assert "Prologue line." in source.chapter_documents[0]["content"]
    assert "The train arrived at dawn." in source.chapter_documents[0]["content"]
