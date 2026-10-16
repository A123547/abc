"""Conservative shared-conditions extraction and non-overwriting merge."""
import re
from datetime import date
from dataclasses import dataclass, field
from app.documents.segmenter import SegmentationResult
from app.schemas.job import JobPosting
from app.services.announcement_metadata import AnnouncementMetadata

@dataclass
class MergeResult:
    job: JobPosting
    reasons: list[str] = field(default_factory=list)

_DEADLINE = re.compile(r'(?:所有岗位|全部岗位|各岗位)报名截止(?:日期|时间)?\s*[：:为至]?\s*(20\d{2})年(\d{1,2})月(\d{1,2})日')
_DEGREE = re.compile(r'(?:所有岗位|全部岗位|各岗位)(?:均)?(?:要求|须具有)\s*(本科及以上|硕士研究生及以上|博士研究生)学历')
_YEAR = re.compile(r'(?:所有岗位|全部岗位|各岗位)(?:均)?(?:面向|限)\s*(20\d{2})届(?:高校)?毕业生')

@dataclass
class CommonConditions:
    deadline: date | None = None
    deadline_quote: str | None = None
    degree: str | None = None
    degree_quote: str | None = None
    year: int | None = None
    year_quote: str | None = None
    warnings: list[str] = field(default_factory=list)

def extract_common(content: str, segmentation: SegmentationResult) -> CommonConditions:
    result = CommonConditions()
    if not segmentation.reliable:
        result.warnings.append('unreliable_segmentation')
        return result
    global_texts = [content[s.span.start:s.span.end] for s in segmentation.sections if s.section_type == 'global']
    text = '\n'.join(global_texts)
    for pattern, key in [(_DEADLINE, 'deadline'), (_DEGREE, 'degree'), (_YEAR, 'year')]:
        found = list(pattern.finditer(text))
        if len(found) > 1:
            result.warnings.append(f'conflicting_or_duplicate_common_{key}')
            continue
        if not found:
            continue
        m = found[0]
        if key == 'deadline':
            try:
                result.deadline = date(*map(int, m.groups()))
                result.deadline_quote = m.group(0)
            except ValueError:
                result.warnings.append('invalid_common_deadline')
        elif key == 'degree':
            result.degree, result.degree_quote = m.group(1), m.group(0)
        else:
            result.year, result.year_quote = int(m.group(1)), m.group(0)
    return result

def merge_job(job: JobPosting, meta: AnnouncementMetadata, common: CommonConditions) -> MergeResult:
    job = job.model_copy(deep=True)
    reasons = list(meta.warnings) + list(common.warnings)
    values = [
        ('organization', meta.organization, meta.organization_quote),
        ('deadline', common.deadline, common.deadline_quote),
        ('degree_required', common.degree, common.degree_quote),
        ('graduation_year', common.year, common.year_quote),
    ]
    for name, shared, quote in values:
        if shared is None:
            continue
        current = getattr(job, name)
        if current is None or current == '':
            setattr(job, name, shared)
            if quote:
                job.evidence[name] = quote
        elif current != shared:
            # Specific field prevails, but conflict is NOT silently trusted.
            reasons.append(f'common_conflict:{name}')
    return MergeResult(job, sorted(set(reasons)))
