
# tests/test_evidence_v2.py

from app.documents.segmenter import segment_document
from app.services.evidence_locator import locate_all
from app.services.ownership_validator import (
    validate_ownership,
)
from app.services.evidence import check_evidence_v2
from app.schemas.job import JobPosting


DOCUMENT = (
    "某能源集团2027届校园招聘。招聘岗位如下："
    "一、综合管理岗。专业要求：社会学、公共管理。"
    "二、财务管理岗。专业要求：会计学、财务管理。"
    "三、技术研发岗。专业要求：软件工程。"
    "所有岗位报名截止日期：2026年11月30日。"
)


def test_segment_count():
    result = segment_document(DOCUMENT)

    jobs = [
        s for s in result.sections
        if s.section_type == "job"
    ]

    assert result.reliable
    assert len(jobs) == 3


def test_segment_complete_coverage():
    result = segment_document(DOCUMENT)

    reconstructed = "".join(
        DOCUMENT[s.span.start:s.span.end]
        for s in result.sections
    )

    assert reconstructed == DOCUMENT


def test_unknown_document():
    result = segment_document(
        "这是一段没有任何职位标题的普通介绍。"
    )

    assert not result.reliable
    assert len(result.sections) == 1
    assert result.sections[0].section_type == "unknown"


def test_locator_multiple_occurrences():
    content = "学历要求：硕士。学历要求：硕士。"

    positions = locate_all(
        content,
        "学历要求：硕士",
    )

    assert len(positions) == 2
    assert positions[0].start != positions[1].start


def test_current_job_evidence():
    result = segment_document(DOCUMENT)

    check = validate_ownership(
        DOCUMENT,
        "专业要求：社会学、公共管理",
        "综合管理岗",
        result.sections,
    )

    assert check.status == "verified_scope"


def test_wrong_job_evidence():
    result = segment_document(DOCUMENT)

    check = validate_ownership(
        DOCUMENT,
        "专业要求：社会学、公共管理",
        "财务管理岗",
        result.sections,
    )

    assert check.status == "wrong_job"


def test_global_evidence():
    result = segment_document(DOCUMENT)

    check = validate_ownership(
        DOCUMENT,
        "所有岗位报名截止日期：2026年11月30日",
        "财务管理岗",
        result.sections,
    )

    assert check.status == "global_scope"


def test_missing_evidence():
    result = segment_document(DOCUMENT)

    check = validate_ownership(
        DOCUMENT,
        "专业要求：经济学",
        "综合管理岗",
        result.sections,
    )

    assert check.status == "not_found"


def test_duplicate_evidence_ambiguous():
    content = (
        "一、综合管理岗。学历要求：硕士。"
        "二、财务管理岗。学历要求：硕士。"
    )

    result = segment_document(content)

    check = validate_ownership(
        content,
        "学历要求：硕士",
        "综合管理岗",
        result.sections,
    )

    assert check.status == "ambiguous"


def test_unreliable_segmentation_requires_review():
    content = (
        "招聘公司拟开展校园招聘活动，"
        "具体安排另行发布。"
    )

    result = segment_document(content)

    job = JobPosting(
        organization="招聘公司",
        position="综合管理岗",
        evidence={"organization": "招聘公司"},
    )

    _, needs_review, reasons = check_evidence_v2(
        content,
        job,
        result.sections,
        result.reliable,
    )

    assert needs_review
    assert "unreliable_document_segmentation" in reasons


def test_cross_job_error_requires_review():
    result = segment_document(DOCUMENT)

    job = JobPosting(
        organization="某能源集团",
        position="财务管理岗",
        majors=["社会学", "公共管理"],
        evidence={
            "majors": "专业要求：社会学、公共管理",
        },
    )

    checks, needs_review, reasons = check_evidence_v2(
        DOCUMENT,
        job,
        result.sections,
        result.reliable,
    )

    assert needs_review
    assert any(
        c.field == "majors"
        and c.ownership_status == "wrong_job"
        for c in checks
    )
    assert "majors:wrong_job" in reasons


def test_first_job_after_colon():
    """岗位列表引导语后是冒号时，不应漏掉第一个岗位。"""

    content = (
        "招聘岗位如下：一、综合管理岗。"
        "专业要求：社会学。"
        "二、财务管理岗。"
        "专业要求：会计学。"
        "三、技术研发岗。"
        "专业要求：软件工程。"
    )

    result = segment_document(content)

    jobs = [
        section
        for section in result.sections
        if section.section_type == "job"
    ]

    assert result.reliable
    assert len(jobs) == 3

    assert [job.job_title for job in jobs] == [
        "综合管理岗",
        "财务管理岗",
        "技术研发岗",
    ]

    assert "".join(
        content[s.span.start:s.span.end]
        for s in result.sections
    ) == content
