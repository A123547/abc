
# tests/test_extraction_pipeline.py

import pytest

from app.schemas.job import JobPosting
from app.services import extraction_pipeline as pipeline


DOCUMENT = (
    "某能源集团2027届校园招聘。招聘岗位如下："
    "一、综合管理岗。专业要求：社会学。"
    "二、财务管理岗。专业要求：会计学。"
    "三、技术研发岗。专业要求：软件工程。"
    "所有岗位报名截止日期：2026年11月30日。"
)


def fake_job(text: str) -> JobPosting:
    mapping = {
        "综合管理岗": ("社会学", "专业要求：社会学"),
        "财务管理岗": ("会计学", "专业要求：会计学"),
        "技术研发岗": ("软件工程", "专业要求：软件工程"),
    }

    for title, (major, quote) in mapping.items():
        if title in text:
            return JobPosting(
                position=title,
                majors=[major],
                evidence={
                    "position": title,
                    "majors": quote,
                },
            )

    raise AssertionError("Unexpected text")


@pytest.mark.asyncio
async def test_segmented_extraction(monkeypatch):

    calls = []

    async def fake_extract(content):
        calls.append(content)
        return [fake_job(content)]

    monkeypatch.setattr(
        pipeline,
        "extract_jobs",
        fake_extract,
    )

    result = await pipeline.extract_document(DOCUMENT)

    assert result.mode == "segmented"
    assert len(result.jobs) == 3
    assert len(calls) == 3

    assert [
        item.job.position
        for item in result.jobs
    ] == [
        "综合管理岗",
        "财务管理岗",
        "技术研发岗",
    ]


@pytest.mark.asyncio
async def test_common_deadline_inheritance(monkeypatch):

    async def fake_extract(content):
        return [fake_job(content)]

    monkeypatch.setattr(
        pipeline,
        "extract_jobs",
        fake_extract,
    )

    result = await pipeline.extract_document(DOCUMENT)

    for item in result.jobs:
        assert str(item.job.deadline) == "2026-11-30"
        assert "deadline" in item.job.evidence

        deadline_checks = [
            c for c in item.evidence_checks
            if c.field == "deadline"
        ]

        assert len(deadline_checks) == 1
        assert (
            deadline_checks[0].ownership_status
            == "global_scope"
        )

        # 公共规则尚未完全验证适用范围
        assert item.review_required


@pytest.mark.asyncio
async def test_unreliable_document_fallback(monkeypatch):

    content = (
        "某公司计划开展招聘活动。"
        "招聘综合管理岗，专业要求社会学。"
    )

    calls = []

    async def fake_extract(text):
        calls.append(text)
        return [
            JobPosting(
                organization="某公司",
                position="综合管理岗",
            )
        ]

    monkeypatch.setattr(
        pipeline,
        "extract_jobs",
        fake_extract,
    )

    result = await pipeline.extract_document(content)

    assert result.mode == "fallback"
    assert len(calls) == 1
    assert calls[0] == content
    assert result.jobs[0].review_required
    assert (
        "whole_document_fallback"
        in result.jobs[0].review_reasons
    )


@pytest.mark.asyncio
async def test_section_title_mismatch_fallback(monkeypatch):

    calls = []

    async def fake_extract(content):
        calls.append(content)

        if content == DOCUMENT:
            return [
                JobPosting(
                    position="综合管理岗"
                )
            ]

        return [
            JobPosting(
                position="错误岗位名称"
            )
        ]

    monkeypatch.setattr(
        pipeline,
        "extract_jobs",
        fake_extract,
    )

    result = await pipeline.extract_document(DOCUMENT)

    assert result.mode == "fallback"
    assert calls[-1] == DOCUMENT
    assert result.jobs[0].review_required
    assert (
        "section_title_mismatch"
        in result.jobs[0].review_reasons
    )
