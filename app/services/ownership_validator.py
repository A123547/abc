
# app/services/ownership_validator.py

from typing import Literal

from pydantic import BaseModel, Field

from app.documents.segmenter import (
    JobSection,
    TextSpan,
    normalize_title,
)
from app.services.evidence_locator import locate_all


OwnershipStatus = Literal[
    "verified_scope",
    "wrong_job",
    "global_scope",
    "ambiguous",
    "not_found",
]


class OwnershipResult(BaseModel):
    status: OwnershipStatus
    locations: list[TextSpan] = Field(
        default_factory=list
    )
    matched_section_ids: list[str] = Field(
        default_factory=list
    )
    reasons: list[str] = Field(default_factory=list)


def find_containing_section(
    span: TextSpan,
    sections: list[JobSection],
) -> JobSection | None:
    """定位完整包含证据区间的文本分段。"""

    for section in sections:
        if (
            section.span.start <= span.start
            and span.end <= section.span.end
        ):
            return section

    return None


def validate_ownership(
    content: str,
    quote: str,
    job_title: str | None,
    sections: list[JobSection],
) -> OwnershipResult:

    locations = locate_all(content, quote)

    if not locations:
        return OwnershipResult(
            status="not_found",
            reasons=["quote_not_in_document"],
        )

    # 根据岗位标题确定候选区间
    candidate_jobs = [
        section
        for section in sections
        if (
            section.section_type == "job"
            and normalize_title(section.job_title or "")
            == normalize_title(job_title or "")
        )
    ]

    section_ids = set()
    kinds = set()

    for location in locations:
        section = find_containing_section(
            location,
            sections,
        )

        if section is None:
            kinds.add("unknown")
            continue

        section_ids.add(section.section_id)
        kinds.add(section.section_type)

    matched_ids = sorted(section_ids)

    # 不能确定目标岗位身份时拒绝自动通过
    if len(candidate_jobs) != 1:
        return OwnershipResult(
            status="ambiguous",
            locations=locations,
            matched_section_ids=matched_ids,
            reasons=["target_job_not_unique_or_missing"],
        )

    target_id = candidate_jobs[0].section_id

    # 重复引用暂时保守处理，不自行选择其中一处
    if len(locations) > 1:
        return OwnershipResult(
            status="ambiguous",
            locations=locations,
            matched_section_ids=matched_ids,
            reasons=["multiple_quote_occurrences"],
        )

    if "unknown" in kinds or len(matched_ids) != 1:
        return OwnershipResult(
            status="ambiguous",
            locations=locations,
            matched_section_ids=matched_ids,
            reasons=["unresolved_evidence_scope"],
        )

    actual_id = matched_ids[0]
    actual_section = next(
        s for s in sections
        if s.section_id == actual_id
    )

    if actual_section.section_type == "global":
        return OwnershipResult(
            status="global_scope",
            locations=locations,
            matched_section_ids=matched_ids,
            reasons=["global_condition_requires_review"],
        )

    if actual_id == target_id:
        return OwnershipResult(
            status="verified_scope",
            locations=locations,
            matched_section_ids=matched_ids,
        )

    if actual_section.section_type == "job":
        return OwnershipResult(
            status="wrong_job",
            locations=locations,
            matched_section_ids=matched_ids,
            reasons=[
                f"evidence_belongs_to_{actual_id}"
            ],
        )

    return OwnershipResult(
        status="ambiguous",
        locations=locations,
        matched_section_ids=matched_ids,
        reasons=["unknown_evidence_scope"],
    )
