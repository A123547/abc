"""Conservative document-level metadata extraction; no LLM guesses."""
import re
from dataclasses import dataclass, field
from app.documents.segmenter import SegmentationResult

@dataclass
class AnnouncementMetadata:
    organization: str | None = None
    organization_quote: str | None = None
    recruitment_year: int | None = None
    warnings: list[str] = field(default_factory=list)

_HEAD = re.compile(r'(?P<org>[^。；;：:\n]{2,45}?(?:集团|有限公司|股份公司|银行|研究院|事业单位))(?P<year>20\d{2})届(?:校园)?招聘')

def extract_metadata(content: str, segmentation: SegmentationResult) -> AnnouncementMetadata:
    prefix = ''.join(content[s.span.start:s.span.end] for s in segmentation.sections if s.section_type == 'global' and s.section_id != 'global_tail')
    matches = list(_HEAD.finditer(prefix))
    if len(matches) != 1:
        return AnnouncementMetadata(warnings=['organization_unresolved'])
    m = matches[0]
    # Keep exact quotation so existing evidence locator can find it.
    return AnnouncementMetadata(organization=m.group('org'), organization_quote=m.group(0), recruitment_year=int(m.group('year')))
