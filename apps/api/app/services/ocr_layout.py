"""Layout reconstruction for OCR output.

RapidOCR returns text lines with bounding boxes in an order that interleaves the
columns of two-column pages. These helpers rebuild reading order: detect the gutter,
read each column top to bottom, keep label/amount pairs that share a row together,
and treat lines that span the gutter as section separators.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass
from difflib import SequenceMatcher

GUTTER_BINS = 200
GUTTER_SEARCH = (0.3, 0.7)
NARROW_LINE_RATIO = 0.55
MIN_SIDE_SHARE = 0.2
HEADER_BAND = 0.11
FOOTER_BAND = 0.07

_DIGIT_GROUP = re.compile(r"(?<![A-Za-z])[0-9oO](?:[0-9oO,.]*[0-9oO])?(?![A-Za-z])")


@dataclass(frozen=True)
class OcrLine:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    score: float = 1.0

    @property
    def height(self) -> float:
        return max(1.0, self.y1 - self.y0)

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2


@dataclass
class PageLayout:
    text: str
    columns: int
    line_count: int
    mean_confidence: float | None
    low_confidence_lines: int
    printed_page: str | None


def lines_from_rapidocr(result) -> list[OcrLine]:
    lines: list[OcrLine] = []
    for item in result or []:
        if len(item) < 2:
            continue
        text = str(item[1]).strip()
        if not text:
            continue
        box = item[0]
        xs = [float(point[0]) for point in box]
        ys = [float(point[1]) for point in box]
        score = float(item[2]) if len(item) > 2 and item[2] is not None else 1.0
        lines.append(OcrLine(text, min(xs), min(ys), max(xs), max(ys), score))
    return lines


def find_gutter(lines: list[OcrLine], width: float) -> float | None:
    narrow = [line for line in lines if (line.x1 - line.x0) < NARROW_LINE_RATIO * width]
    if len(narrow) < 6:
        return None
    cover = [0] * GUTTER_BINS
    for line in narrow:
        start = max(0, int(line.x0 / width * GUTTER_BINS))
        end = min(GUTTER_BINS - 1, int(line.x1 / width * GUTTER_BINS))
        for index in range(start, end + 1):
            cover[index] += 1
    allowed = max(1, round(0.02 * len(narrow)))
    lo, hi = (int(GUTTER_SEARCH[0] * GUTTER_BINS), int(GUTTER_SEARCH[1] * GUTTER_BINS))
    best: tuple[int, int] | None = None
    run_start: int | None = None
    for index in range(lo, hi + 1):
        if cover[index] <= allowed:
            run_start = index if run_start is None else run_start
            if best is None or (index - run_start) > (best[1] - best[0]):
                best = (run_start, index)
        else:
            run_start = None
    if best is None or best[1] - best[0] < 1:
        return None
    gutter = (best[0] + best[1] + 1) / 2 / GUTTER_BINS * width
    left = sum(1 for line in narrow if line.x1 <= gutter)
    right = sum(1 for line in narrow if line.x0 >= gutter)
    if min(left, right) < MIN_SIDE_SHARE * len(narrow):
        return None
    return gutter


def _rows(lines: list[OcrLine], median_height: float) -> list[list[OcrLine]]:
    rows: list[list[OcrLine]] = []
    for line in sorted(lines, key=lambda item: (item.cy, item.x0)):
        if rows and abs(line.cy - statistics.mean(member.cy for member in rows[-1])) < 0.5 * median_height:
            rows[-1].append(line)
        else:
            rows.append([line])
    return [sorted(row, key=lambda item: item.x0) for row in rows]


def _render(lines: list[OcrLine], median_height: float) -> str:
    out: list[str] = []
    previous_bottom: float | None = None
    for row in _rows(lines, median_height):
        text = " ".join(member.text for member in row)
        top = min(member.y0 for member in row)
        if previous_bottom is not None:
            gap = top - previous_bottom
            out.append("\n\n" if gap > 0.8 * median_height or is_section_heading(text) else "\n")
        out.append(text)
        previous_bottom = max(member.y1 for member in row)
    return "".join(out)


def order_lines(lines: list[OcrLine], width: float) -> tuple[str, int]:
    if not lines:
        return "", 0
    median_height = statistics.median(line.height for line in lines)
    gutter = find_gutter(lines, width)
    if gutter is None:
        return _render(lines, median_height), 1
    tolerance = 0.01 * width
    spanning = sorted(
        (line for line in lines if line.x0 < gutter - tolerance and line.x1 > gutter + tolerance),
        key=lambda item: item.cy,
    )
    spanning_ids = {id(line) for line in spanning}
    rest = [line for line in lines if id(line) not in spanning_ids]
    bounds = [float("-inf"), *(line.cy for line in spanning), float("inf")]
    blocks: list[str] = []
    for index in range(len(bounds) - 1):
        top, bottom = bounds[index], bounds[index + 1]
        segment = [line for line in rest if top <= line.cy < bottom]
        left = [line for line in segment if (line.x0 + line.x1) / 2 < gutter]
        right = [line for line in segment if (line.x0 + line.x1) / 2 >= gutter]
        for column in (left, right):
            if column:
                blocks.append(_render(column, median_height))
        if index < len(spanning):
            blocks.append(spanning[index].text)
    return "\n\n".join(block for block in blocks if block.strip()), 2


def margin_key(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.lower())


def _similar(left: str, right: str) -> bool:
    if left == right:
        return True
    if min(len(left), len(right)) >= 8 and (left in right or right in left):
        return True
    return SequenceMatcher(None, left, right).ratio() >= 0.8


def matches_repeated_margin(key: str, repeated: set[str]) -> bool:
    return bool(key) and any(_similar(key, candidate) for candidate in repeated)


def split_margins(lines: list[OcrLine], height: float) -> tuple[list[OcrLine], list[OcrLine]]:
    body: list[OcrLine] = []
    margins: list[OcrLine] = []
    for line in lines:
        if line.cy < HEADER_BAND * height or line.cy > (1 - FOOTER_BAND) * height:
            margins.append(line)
        else:
            body.append(line)
    return body, margins


def layout_page(
    lines: list[OcrLine],
    width: float,
    height: float,
    repeated_margins: set[str],
    *,
    low_confidence: float = 0.6,
) -> PageLayout:
    body, margins = split_margins(lines, height)
    printed_page = None
    kept_margins: list[OcrLine] = []
    for line in margins:
        compact = line.text.strip()
        if line.cy > (1 - FOOTER_BAND) * height and re.fullmatch(r"\d{1,3}", compact):
            printed_page = compact
            continue
        key = margin_key(compact)
        if not key or matches_repeated_margin(key, repeated_margins):
            continue
        kept_margins.append(line)
    text, columns = order_lines([*kept_margins, *body], width)
    scores = [line.score for line in lines]
    return PageLayout(
        text=text,
        columns=columns,
        line_count=len(lines),
        mean_confidence=round(statistics.mean(scores), 4) if scores else None,
        low_confidence_lines=sum(1 for score in scores if score < low_confidence),
        printed_page=printed_page,
    )


def repeated_margin_keys(pages: list[tuple[list[OcrLine], float]], *, min_share: float = 0.25) -> set[str]:
    """Margin texts (header/footer bands) that recur, allowing OCR spelling noise, on
    at least `min_share` of pages. Content that appears only once is never removed."""
    per_page: list[set[str]] = []
    for lines, height in pages:
        _body, margins = split_margins(lines, height)
        per_page.append({key for key in (margin_key(line.text) for line in margins) if len(key) >= 4})
    threshold = max(2, int(min_share * len(pages)))
    repeated: set[str] = set()
    for key in set().union(*per_page) if per_page else set():
        count = sum(1 for keys in per_page if any(_similar(key, other) for other in keys))
        if count >= threshold:
            repeated.add(key)
    return repeated


def fix_digit_confusions(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Replace letter o/O with zero only inside digit groups that already contain two digits.

    "Rs.5,00o/-" -> "Rs.5,000/-" and "12,ooo" -> "12,000"; words, ordinals such as
    "1oth", and isolated letters are left untouched. Every change is returned so the
    caller can report it.
    """
    changes: list[tuple[str, str]] = []

    def replace(match: re.Match[str]) -> str:
        token = match.group(0)
        if "o" not in token and "O" not in token:
            return token
        if sum(char.isdigit() for char in token) < 2:
            return token
        fixed = token.replace("o", "0").replace("O", "0")
        changes.append((token, fixed))
        return fixed

    return _DIGIT_GROUP.sub(replace, text), changes


_NUMBERED_HEADING = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){1,3})\.?\s*([A-Z].{2,90})$")


def is_section_heading(line: str) -> bool:
    return section_heading(line) is not None


def section_heading(line: str) -> tuple[str, str] | None:
    """Return (number, title) for numbered headings such as '8.1 FEE AND CHARGES'."""
    match = _NUMBERED_HEADING.match(line.strip())
    if not match:
        return None
    number, title = match.group(1), match.group(2).strip()
    if title.endswith((".", ",", ";")):
        return None
    letters = [char for char in title if char.isalpha()]
    if len(letters) < 3 or not title[0].isupper():
        return None
    upper_ratio = sum(1 for char in letters if char.isupper()) / len(letters)
    words = [word for word in re.split(r"\s+", title) if word[:1].isalpha()]
    capitalised = sum(1 for word in words if word[0].isupper()) / max(1, len(words))
    if upper_ratio >= 0.5 or (capitalised >= 0.6 and len(title) <= 60):
        return number, title
    return None
