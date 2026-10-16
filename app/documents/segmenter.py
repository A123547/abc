
# app/documents/segmenter.py

import re
from typing import Literal

from pydantic import BaseModel, Field


class TextSpan(BaseModel):
    start: int
    end: int


class JobSection(BaseModel):
    section_id: str
    section_type: Literal["global", "job", "unknown"]
    span: TextSpan
    job_title: str | None = None


class SegmentationResult(BaseModel):
    sections: list[JobSection] = Field(default_factory=list)
    reliable: bool = False
    reasons: list[str] = Field(default_factory=list)


# 例如：一、综合管理岗。 二、财务管理岗。

NUMBERED_JOB = re.compile(
    r"(?:(?<=\A)|(?<=[。；;：:\n]))\s*"
    r"(?P<number>[一二三四五六七八九十]{1,3})、"
    r"\s*(?P<title>[^。\n；;：:]{2,35}?岗)"
    r"\s*(?=[。；;：:\n])"
)


# 例如：岗位名称：人力资源管理岗
LABELED_JOB = re.compile(
    r"岗位名称\s*[：:]\s*"
    r"(?P<title>[^\s。，；;\n]{2,35}?岗)"
)

# 明确适用于所有岗位的尾部条件
GLOBAL_TAIL = re.compile(
    r"(?:^|[。；;\n])\s*"
    r"(?P<header>所有岗位|全部岗位|各岗位)"
    r"(?:报名截止|均须|统一|的报名截止)"
)


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", "", title).strip("：:。；; ")


def _get_job_headers(content: str):
    numbered = list(NUMBERED_JOB.finditer(content))

    # 优先使用编号岗位结构
    if numbered:
        return [
            (m.start("number"), normalize_title(m.group("title")))
            for m in numbered
        ]

    labeled = list(LABELED_JOB.finditer(content))
    return [
        (m.start(), normalize_title(m.group("title")))
        for m in labeled
    ]


def _make_section(
    section_id: str,
    section_type: Literal["global", "job", "unknown"],
    start: int,
    end: int,
    title: str | None = None,
) -> JobSection:
    return JobSection(
        section_id=section_id,
        section_type=section_type,
        span=TextSpan(start=start, end=end),
        job_title=title,
    )


def segment_document(content: str) -> SegmentationResult:
    if not content:
        return SegmentationResult(
            sections=[],
            reliable=False,
            reasons=["empty_document"],
        )

    headers = _get_job_headers(content)

    if not headers:
        return SegmentationResult(
            sections=[
                _make_section(
                    "unknown_0",
                    "unknown",
                    0,
                    len(content),
                )
            ],
            reliable=False,
            reasons=["no_reliable_job_heading"],
        )

    # 发现所有岗位公共条件的明确起始位置
    tail_start = None
    for match in GLOBAL_TAIL.finditer(content):
        pos = match.start("header")
        if pos > headers[-1][0]:
            tail_start = pos
            break

    sections: list[JobSection] = []

    # 第一个岗位标题之前的公告说明
    first_start = headers[0][0]

    if first_start > 0:
        sections.append(
            _make_section(
                "global_0", "global", 0, first_start
            )
        )

    job_end_limit = (
        tail_start if tail_start is not None else len(content)
    )

    for i, (start, title) in enumerate(headers):
        end = (
            headers[i + 1][0]
            if i + 1 < len(headers)
            else job_end_limit
        )

        if start >= end:
            return SegmentationResult(
                sections=[
                    _make_section(
                        "unknown_0",
                        "unknown",
                        0,
                        len(content),
                    )
                ],
                reliable=False,
                reasons=["invalid_section_boundaries"],
            )

        sections.append(
            _make_section(
                f"job_{i + 1}",
                "job",
                start,
                end,
                title,
            )
        )

    if tail_start is not None:
        sections.append(
            _make_section(
                "global_tail",
                "global",
                tail_start,
                len(content),
            )
        )

    # 验证分段没有空洞或者重叠
    cursor = 0
    for section in sections:
        if section.span.start != cursor:
            return SegmentationResult(
                sections=[
                    _make_section(
                        "unknown_0",
                        "unknown",
                        0,
                        len(content),
                    )
                ],
                reliable=False,
                reasons=["coverage_validation_failed"],
            )
        cursor = section.span.end

    if cursor != len(content):
        return SegmentationResult(
            sections=[
                _make_section(
                    "unknown_0",
                    "unknown",
                    0,
                    len(content),
                )
            ],
            reliable=False,
            reasons=["incomplete_coverage"],
        )

    titles = [
        section.job_title
        for section in sections
        if section.section_type == "job"
    ]

    reasons = []
    if len(titles) != len(set(titles)):
        reasons.append("duplicate_job_titles")

    return SegmentationResult(
        sections=sections,
        reliable=not reasons,
        reasons=reasons,
    )
