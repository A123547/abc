
# app/services/extraction_pipeline.py

import re

from pydantic import BaseModel, Field

from app.documents.segmenter import (
    JobSection,
    SegmentationResult,
    segment_document,
)
from app.schemas.job import (ExtractedJob,ExtractionResponse,JobPosting,)
from app.services.evidence import check_evidence_v2
from app.services.extraction import extract_jobs

from app.services.announcement_metadata import extract_metadata
from app.services.common_conditions import extract_common, merge_job
from app.services.semantic_validator import validate_semantics

class PipelineResult(BaseModel):
    jobs: list[ExtractedJob]
    mode: str
    reasons: list[str] = Field(default_factory=list)


# 仅识别明确声明适用于全部岗位的截止日期。
# 暂不支持日期范围、延期公告或复杂报名规则。
GLOBAL_DEADLINE = re.compile(
    r"(?:所有岗位|全部岗位|各岗位)"
    r"报名截止(?:日期|时间)?"
    r"\s*[：:为至]?\s*"
    r"(?P<year>20\d{2})年"
    r"(?P<month>\d{1,2})月"
    r"(?P<day>\d{1,2})日"
)


def get_section_text(
    content: str,
    section: JobSection,
) -> str:
    return content[
        section.span.start:section.span.end
    ]


def get_common_deadline(
    content: str,
    segmentation: SegmentationResult,
):
    """只解析明确的公共截止日期。"""

    from datetime import date

    candidates = []

    for section in segmentation.sections:
        if section.section_type != "global":
            continue

        text = get_section_text(content, section)

        for match in GLOBAL_DEADLINE.finditer(text):
            try:
                value = date(
                    int(match.group("year")),
                    int(match.group("month")),
                    int(match.group("day")),
                )
            except ValueError:
                continue

            candidates.append(
                (value, match.group(0))
            )

    # 必须只有一个明确、无冲突的公共日期
    if len(candidates) != 1:
        return None

    return candidates[0]


def merge_common_fields(
    job: JobPosting,
    common_deadline,
) -> JobPosting:
    """不覆盖岗位已经明确提取的私有字段。"""

    if common_deadline is None:
        return job

    deadline, quote = common_deadline

    # 明确的岗位截止日期优先于公共日期
    if job.deadline is not None:
        return job

    updated = job.model_copy(deep=True)
    updated.deadline = deadline
    updated.evidence["deadline"] = quote

    return updated


def validate_job(
    content: str,
    job: JobPosting,
    segmentation: SegmentationResult,
    extra_reasons: list[str] | None = None,
) -> ExtractedJob:

    checks, needs_review, reasons = check_evidence_v2(
        content=content,
        job=job,
        sections=segmentation.sections,
        segmentation_reliable=segmentation.reliable,
    )

    all_reasons = sorted(
        set(reasons + (extra_reasons or []))
    )

    return ExtractedJob(
        job=job,
        evidence_checks=checks,
        review_required=(
            needs_review or bool(all_reasons)
        ),
        review_reasons=all_reasons,
    )


async def fallback_extract(
    content: str,
    segmentation: SegmentationResult,
    reason: str,
) -> PipelineResult:
    """回退整篇提取，但不能自动视为已核验。"""

    jobs = await extract_jobs(content)

    results = [
        validate_job(
            content,
            job,
            segmentation,
            extra_reasons=[
                "whole_document_fallback",
                reason,
            ],
        )
        for job in jobs
    ]

    return PipelineResult(
        jobs=results,
        mode="fallback",
        reasons=[reason],
    )



async def extract_document(
    content: str,
) -> PipelineResult:

    # 1. 对完整公告进行确定性分段
    segmentation = segment_document(content)

    sections = [
        section
        for section in segmentation.sections
        if section.section_type == "job"
    ]

    # 2. 分段不可靠，回退到整篇提取
    if not segmentation.reliable or not sections:
        return await fallback_extract(
            content,
            segmentation,
            "unreliable_segmentation",
        )

    # 3. 提取公告级元数据
    # 例如招聘单位、招聘批次
    metadata = extract_metadata(
        content,
        segmentation,
    )

    # 4. 提取明确适用于全部岗位的公共条件
    # 例如统一报名截止日期、统一学历条件
    common_conditions = extract_common(
        content,
        segmentation,
    )

    extracted_jobs = []
    merge_reasons = []

    # 5. 分别解析每个岗位
    for section in sections:

        section_text = get_section_text(
            content,
            section,
        )

        jobs = await extract_jobs(section_text)

        # 每个明确的岗位区间应对应一个职位
        if len(jobs) != 1:
            return await fallback_extract(
                content,
                segmentation,
                "section_job_count_mismatch",
            )

        job = jobs[0]

        # 6. 检查模型提取的岗位身份
        if job.position != section.job_title:
            return await fallback_extract(
                content,
                segmentation,
                "section_title_mismatch",
            )

        # 7. 合并公告元数据、公共条件
        merged = merge_job(
            job,
            metadata,
            common_conditions,
        )

        job = merged.job

        extracted_jobs.append(job)

        # 保留公共条件冲突等复核原因
        merge_reasons.append(merged.reasons)

    # 8. 检查岗位数量一致性
    if len(extracted_jobs) != len(sections):
        return await fallback_extract(
            content,
            segmentation,
            "document_job_count_mismatch",
        )

    results = []

    # 9. 对每个岗位进行证据与语义核验
    for job, merging_reasons in zip(
        extracted_jobs,
        merge_reasons,
    ):

        # 判断字段值与原文引用是否一致
        semantic_result = validate_semantics(job)

        # 合并所有复核原因
        extra_reasons = (
            merging_reasons
            + semantic_result.reasons
        )

        # 执行原有 Evidence Engine V2
        result = validate_job(
            content=content,
            job=job,
            segmentation=segmentation,
            extra_reasons=extra_reasons,
        )

        results.append(result)

    # 10. 输出完整的岗位提取结果
    return PipelineResult(
        jobs=results,
        mode="segmented",
    )
