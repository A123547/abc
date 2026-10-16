
from datetime import date
from typing import Literal
from pydantic import BaseModel, Field
from app.documents.segmenter import TextSpan

class JobPosting(BaseModel):
    """结构化招聘岗位。"""

    organization: str | None = None
    position: str | None = None
    city: str | None = None

    degree_required: str | None = None
    majors: list[str] = Field(default_factory=list)
    graduation_year: int | None = None

    headcount: int | None = None
    deadline: date | None = None

    # 字段名称 -> 原文证据片段
    evidence: dict[str, str] = Field(
        default_factory=dict
    )


class ExtractionRequest(BaseModel):
    """用户提交的招聘公告。"""

    content: str = Field(
        min_length=30,
        max_length=50000,
    )
    source_url: str | None = None


class EvidenceCheck(BaseModel):
    field: str
    quote: str
    status: Literal["found", "not_found"]
    # V2 新增
    ownership_status: Literal[
        "verified_scope",
        "wrong_job",
        "global_scope",
        "ambiguous",
        "not_found",
    ] = "ambiguous"

    locations: list[TextSpan] = Field(
        default_factory=list
    )
    matched_section_ids: list[str] = Field(
        default_factory=list
    )
    reasons: list[str] = Field(
        default_factory=list
    )

class ExtractedJob(BaseModel):
    job: JobPosting
    evidence_checks: list[EvidenceCheck]
    review_required: bool
    # V2 新增
    review_reasons: list[str] = Field(
        default_factory=list
    )


class ExtractionResponse(BaseModel):
    source_url: str | None = None
    jobs: list[ExtractedJob]
    total: int
