from datetime import date
from app.documents.segmenter import segment_document
from app.schemas.job import JobPosting
from app.services.announcement_metadata import extract_metadata
from app.services.common_conditions import extract_common, merge_job
from app.services.semantic_validator import validate_semantics

DOC = ('某能源集团2027届校园招聘。招聘岗位如下：'
       '一、综合管理岗。专业要求：社会学。'
       '二、财务管理岗。专业要求：会计学。'
       '所有岗位报名截止日期：2026年11月30日。')

def test_announcement_metadata():
    s = segment_document(DOC)
    m = extract_metadata(DOC, s)
    assert m.organization == '某能源集团'
    assert m.recruitment_year == 2027

def test_common_deadline_inherited():
    s = segment_document(DOC)
    m = extract_metadata(DOC, s)
    c = extract_common(DOC, s)
    merged = merge_job(JobPosting(position='综合管理岗'), m, c)
    assert merged.job.deadline == date(2026, 11, 30)
    assert merged.job.organization == '某能源集团'
    assert not any('common_conflict' in r for r in merged.reasons)

def test_specific_deadline_conflict():
    s = segment_document(DOC)
    m = extract_metadata(DOC, s)
    c = extract_common(DOC, s)
    job = JobPosting(position='综合管理岗', deadline=date(2026, 12, 1))
    merged = merge_job(job, m, c)
    assert merged.job.deadline == date(2026, 12, 1)
    assert 'common_conflict:deadline' in merged.reasons

def test_no_generic_year_from_heading():
    s = segment_document(DOC)
    c = extract_common(DOC, s)
    assert c.year is None  # 2027届校园招聘标题不是全部岗位的明确资格条件

def test_degree_false_upgrade_detected():
    job = JobPosting(degree_required='硕士研究生及以上', evidence={'degree_required':'学历要求：本科及以上'})
    assert 'semantic_conflict:degree_required' in validate_semantics(job).reasons

def test_major_mismatch_detected():
    job = JobPosting(majors=['社会学'], evidence={'majors':'专业要求：会计学'})
    assert 'semantic_unknown:majors' in validate_semantics(job).reasons

def test_unrestricted_major_not_enumerated():
    job = JobPosting(majors=['社会学'], evidence={'majors':'专业不限'})
    assert 'semantic_conflict:majors' in validate_semantics(job).reasons

def test_date_conflict():
    job = JobPosting(deadline=date(2026,11,15), evidence={'deadline':'报名截止日期：2026年11月30日'})
    assert 'semantic_conflict:deadline' in validate_semantics(job).reasons
