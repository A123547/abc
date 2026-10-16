
# app/services/evidence_locator.py

from app.documents.segmenter import TextSpan


def locate_all(
    content: str,
    quote: str,
) -> list[TextSpan]:
    """查找原文引用的所有匹配位置，支持重叠匹配。"""

    if not quote:
        return []

    spans = []
    offset = 0

    while True:
        start = content.find(quote, offset)

        if start == -1:
            break

        spans.append(
            TextSpan(
                start=start,
                end=start + len(quote),
            )
        )

        offset = start + 1

    return spans
