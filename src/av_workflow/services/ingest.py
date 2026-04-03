from __future__ import annotations

import re

from av_workflow.contracts.models import Job, SourceDocument

_CHAPTER_HEADING_PATTERN = re.compile(
    r"^(chapter\s+\d+(?:[:\s-].*)?|第[0-9一二三四五六七八九十百零]+章.*)$",
    re.IGNORECASE,
)


def normalize_source(
    job: Job,
    raw_text: str,
    *,
    source_document_id: str | None = None,
) -> SourceDocument:
    normalized_text = _normalize_text(raw_text)
    chapter_documents = _split_chapters(normalized_text)
    title = chapter_documents[0]["title"] if chapter_documents else f"{job.job_id}-source"

    return SourceDocument(
        source_document_id=source_document_id or f"{job.job_id}-source-v1",
        job_id=job.job_id,
        source_ref=job.source_ref,
        title=title,
        language=job.language,
        normalized_text=normalized_text,
        chapter_documents=chapter_documents,
        source_metadata={"chapter_count": len(chapter_documents)},
    )


def _normalize_text(raw_text: str) -> str:
    lines = [line.strip() for line in raw_text.splitlines()]
    normalized_lines: list[str] = []
    blank_pending = False

    for line in lines:
        if line:
            if blank_pending and normalized_lines:
                normalized_lines.append("")
            normalized_lines.append(line)
            blank_pending = False
            continue
        blank_pending = True

    return "\n".join(normalized_lines).strip()


def _split_chapters(normalized_text: str) -> list[dict[str, str]]:
    if not normalized_text:
        return [{"chapter_id": "ch-1", "title": "Chapter 1", "content": ""}]

    lines = normalized_text.splitlines()
    detected_headings = [line for line in lines if _CHAPTER_HEADING_PATTERN.match(line)]
    if not detected_headings:
        return [
            {
                "chapter_id": "ch-1",
                "title": "Chapter 1",
                "content": normalized_text,
            }
        ]

    chapters: list[dict[str, str]] = []
    current_title: str | None = None
    current_content: list[str] = []
    leading_content: list[str] = []

    for line in lines:
        if _CHAPTER_HEADING_PATTERN.match(line):
            if current_title is not None:
                chapters.append(
                    {
                        "chapter_id": f"ch-{len(chapters) + 1}",
                        "title": current_title,
                        "content": "\n".join(current_content).strip(),
                    }
                )
            current_title = line
            current_content = leading_content.copy() if not chapters else []
            leading_content = []
            continue
        if current_title is None:
            leading_content.append(line)
            continue
        current_content.append(line)

    if current_title is not None:
        chapters.append(
            {
                "chapter_id": f"ch-{len(chapters) + 1}",
                "title": current_title,
                "content": "\n".join(current_content).strip(),
            }
        )

    return chapters
