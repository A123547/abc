"""Rule-based semantic consistency checks, deliberately conservative."""
import re
from datetime import date
from dataclasses import dataclass, field
from app.schemas.job import JobPosting

@dataclass
class SemanticResult:
    reasons: list[str] = field(default_factory=list)
    checked_fields: list[str] = field(default_factory=list)

def validate_semantics(job: JobPosting) -> SemanticResult:
    result = SemanticResult()
    evidence = job.evidence
    # A substring hit is not enough: check field-specific values.
    if job.degree_required:
        quote = evidence.get('degree_required', '')
        values = re.findall(r'(?:博士研究生|硕士研究生|本科)(?:及以上)?', quote)
        if not values:
            result.reasons.append('semantic_unknown:degree_required')
        elif job.degree_required not in values:
            result.reasons.append('semantic_conflict:degree_required')
        else:
            result.checked_fields.append('degree_required')
    if job.graduation_year is not None:
        quote = evidence.get('graduation_year', '')
        years = [int(x) for x in re.findall(r'(20\d{2})\s*届', quote)]
        if not years:
            years = [int(x) for x in re.findall(r'(20\d{2})\s*年', quote)]
        if not years:
            result.reasons.append('semantic_unknown:graduation_year')
        elif job.graduation_year not in years:
            result.reasons.append('semantic_conflict:graduation_year')
        else:
            result.checked_fields.append('graduation_year')
    if job.headcount is not None:
        quote = evidence.get('headcount', '')
        nums = [int(x) for x in re.findall(r'(\d+)\s*人', quote)]
        if not nums:
            result.reasons.append('semantic_unknown:headcount')
        elif job.headcount not in nums:
            result.reasons.append('semantic_conflict:headcount')
        else:
            result.checked_fields.append('headcount')
    if job.deadline is not None:
        quote = evidence.get('deadline', '')
        dates = re.findall(r'(20\d{2})年(\d{1,2})月(\d{1,2})日', quote)
        if not dates:
            result.reasons.append('semantic_unknown:deadline')
        else:
            parsed = []
            for parts in dates:
                try:
                    parsed.append(date(*map(int, parts)))
                except ValueError:
                    pass
            if job.deadline not in parsed:
                result.reasons.append('semantic_conflict:deadline')
            else:
                result.checked_fields.append('deadline')
    if job.majors:
        quote = evidence.get('majors', '')
        if '不限' in quote:
            result.reasons.append('semantic_conflict:majors')
        elif not quote or not all(major in quote for major in job.majors):
            result.reasons.append('semantic_unknown:majors')
        else:
            result.checked_fields.append('majors')
    # Organization and city are not asserted semantically by this rule set.
    return result
