from app.documents.segmenter import (
    JobSection,
    segment_document,
)
from app.schemas.job import (
    EvidenceCheck,
    JobPosting,
)
from app.services.ownership_validator import (
    validate_ownership,
)


REQUIRED_EVIDENCE_FIELDS = {
    "organization",
    "position",
    "city",
    "degree_required",
    "majors",
    "graduation_year",
    "headcount",
    "deadline",
}

# 全公告通用的组织名称可以来自公告前言
DOCUMENT_LEVEL_FIELDS = {"organization"}


def check_evidence_v2(
    content: str,
    job: JobPosting,
    sections: list[JobSection],
    segmentation_reliable: bool = True,
) -> tuple[list[EvidenceCheck], bool, list[str]]:

    checks: list[EvidenceCheck] = []
    review_reasons: list[str] = []

    for field, quote in job.evidence.items():
        if field not in REQUIRED_EVIDENCE_FIELDS:
            review_reasons.append(
                f"unsupported_field:{field}"
            )
            continue

        result = validate_ownership(
            content=content,
            quote=quote,
            job_title=job.position,
            sections=sections,
        )

        status = (
            "not_found"
            if result.status == "not_found"
            else "found"
        )

        checks.append(
            EvidenceCheck(
                field=field,
                quote=quote,
                status=status,
                ownership_status=result.status,
                locations=result.locations,
                matched_section_ids=(
                    result.matched_section_ids
                ),
                reasons=result.reasons,
            )
        )

        is_valid_scope = (
            result.status == "verified_scope"
            or (
                field in DOCUMENT_LEVEL_FIELDS
                and result.status == "global_scope"
            )
        )

        if not is_valid_scope:
            review_reasons.append(
                f"{field}:{result.status}"
            )

    for field in REQUIRED_EVIDENCE_FIELDS:
        value = getattr(job, field)

        has_value = (
            value is not None
            and value != ""
            and value != []
        )

        if has_value and not job.evidence.get(field):
            review_reasons.append(
                f"missing_evidence:{field}"
            )

    if not job.organization:
        review_reasons.append(
            "missing_organization"
        )

    if not job.position:
        review_reasons.append(
            "missing_position"
        )

    if not segmentation_reliable:
        review_reasons.append(
            "unreliable_document_segmentation"
        )

    review_reasons = sorted(set(review_reasons))

    return (
        checks,
        bool(review_reasons),
        review_reasons,
    )


# 保留旧版双参数调用方式，避免破坏已有代码
def check_evidence(
    content: str,
    job: JobPosting,
) -> tuple[list[EvidenceCheck], bool]:

    segmentation = segment_document(content)

    checks, needs_review, _ = check_evidence_v2(
        content=content,
        job=job,
        sections=segmentation.sections,
        segmentation_reliable=segmentation.reliable,
    )

    return checks, needs_review