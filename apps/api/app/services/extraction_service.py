from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from app.core.exceptions import ExtractionError
from app.services.ocr_layout import (
    OcrLine,
    fix_digit_confusions,
    layout_page,
    lines_from_rapidocr,
    order_lines,
    repeated_margin_keys,
)
from app.utils.text import looks_like_heading, normalize_text

logger = logging.getLogger(__name__)

OCR_LAYOUT_VERSION = "columns-v1"


@dataclass
class PageExtraction:
    page_number: int
    text: str
    char_count: int
    image_count: int
    is_empty: bool
    needs_ocr: bool
    ocr_used: bool = False
    ocr_error: str | None = None
    ocr_columns: int | None = None
    ocr_confidence: float | None = None
    ocr_low_confidence_lines: int = 0
    digit_fixes: list[tuple[str, str]] = field(default_factory=list)
    printed_page: str | None = None


@dataclass
class ExtractionResult:
    page_count: int
    pages: list[PageExtraction]
    headings: list[str] = field(default_factory=list)
    empty_page_count: int = 0
    ocr_page_count: int = 0
    extractable_char_count: int = 0
    ocr_failed_pages: list[int] = field(default_factory=list)
    config: dict = field(default_factory=dict)


@dataclass
class _OcrPage:
    lines: list[OcrLine]
    width: float
    height: float


class ExtractionService:
    empty_text_threshold = 0
    ocr_char_threshold = 40

    def __init__(
        self,
        *,
        ocr_cache_dir: Path | None = None,
        ocr_scale: float = 1.6,
        column_aware: bool = True,
        fix_ocr_digits: bool = True,
    ) -> None:
        self.ocr_cache_dir = ocr_cache_dir
        self.ocr_scale = ocr_scale
        self.column_aware = column_aware
        self.fix_ocr_digits = fix_ocr_digits

    def config(self) -> dict:
        return {
            "ocr_engine": "rapidocr_onnxruntime",
            "ocr_scale": self.ocr_scale,
            "ocr_layout": OCR_LAYOUT_VERSION if self.column_aware else "engine-order",
            "fix_ocr_digits": self.fix_ocr_digits,
            "ocr_char_threshold": self.ocr_char_threshold,
        }

    def extract_pdf(self, path: Path) -> ExtractionResult:
        try:
            import fitz
        except ImportError as exc:  # pragma: no cover
            raise ExtractionError("PyMuPDF is not installed.") from exc

        try:
            document = fitz.open(path)
        except Exception as exc:
            raise ExtractionError("The PDF could not be opened. It may be damaged or encrypted.") from exc

        cache_dir = self._cache_dir_for(path)
        try:
            if document.is_encrypted:
                raise ExtractionError("Encrypted PDFs are not supported.")
            if document.page_count == 0:
                raise ExtractionError("The PDF contains no pages.")

            pages: list[PageExtraction] = []
            ocr_pages: dict[int, _OcrPage] = {}
            for index in range(document.page_count):
                page = document.load_page(index)
                text = normalize_text(page.get_text("text") or "")
                images = page.get_images(full=True)
                record = PageExtraction(
                    page_number=index + 1,
                    text=text,
                    char_count=len(text),
                    image_count=len(images),
                    is_empty=False,
                    needs_ocr=False,
                )
                if len(text) < self.ocr_char_threshold and images:
                    try:
                        ocr_pages[record.page_number] = self._ocr_page(page, cache_dir)
                    except Exception as exc:
                        record.ocr_error = f"{type(exc).__name__}: {exc}"[:300]
                        logger.warning("OCR failed on page %s: %s", record.page_number, record.ocr_error)
                pages.append(record)
        finally:
            document.close()

        repeated = repeated_margin_keys([(item.lines, item.height) for item in ocr_pages.values()])
        headings: list[str] = []
        for record in pages:
            ocr = ocr_pages.get(record.page_number)
            if ocr is not None and ocr.lines:
                self._apply_ocr(record, ocr, repeated)
            record.char_count = len(record.text)
            record.is_empty = record.char_count <= self.empty_text_threshold
            record.needs_ocr = (
                record.char_count < self.ocr_char_threshold and record.image_count > 0 and not record.ocr_used
            )
            for line in record.text.split("\n"):
                if looks_like_heading(line) and line.strip() not in headings:
                    headings.append(line.strip())

        extractable = sum(page.char_count for page in pages)
        failed = [page.page_number for page in pages if page.ocr_error]
        if extractable == 0:
            raise ExtractionError(
                "No extractable text was found. The PDF may be scanned; OCR is required before indexing.",
                details={"page_count": len(pages), "ocr_failed_pages": failed},
            )

        return ExtractionResult(
            page_count=len(pages),
            pages=pages,
            headings=headings[:12],
            empty_page_count=sum(1 for page in pages if page.is_empty),
            ocr_page_count=sum(1 for page in pages if page.ocr_used),
            extractable_char_count=extractable,
            ocr_failed_pages=failed,
            config=self.config(),
        )

    def _apply_ocr(self, record: PageExtraction, ocr: _OcrPage, repeated: set[str]) -> None:
        if self.column_aware:
            layout = layout_page(ocr.lines, ocr.width, ocr.height, repeated)
            text = layout.text
            record.ocr_columns = layout.columns
            record.ocr_confidence = layout.mean_confidence
            record.ocr_low_confidence_lines = layout.low_confidence_lines
            record.printed_page = layout.printed_page
        else:
            text = "\n".join(line.text for line in ocr.lines)
        if self.fix_ocr_digits:
            text, record.digit_fixes = fix_digit_confusions(text)
        text = normalize_text(text)
        if text:
            record.text = text
            record.ocr_used = True

    def _cache_dir_for(self, path: Path) -> Path | None:
        if self.ocr_cache_dir is None:
            return None
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
        return self.ocr_cache_dir / digest / f"scale-{self.ocr_scale}"

    def _ocr_page(self, page, cache_dir: Path | None) -> _OcrPage:
        cache_file = cache_dir / f"page-{page.number + 1:04d}.json" if cache_dir else None
        if cache_file is not None and cache_file.is_file():
            payload = json.loads(cache_file.read_text(encoding="utf-8"))
            return _OcrPage(
                lines=[OcrLine(*row) for row in payload["lines"]],
                width=payload["width"],
                height=payload["height"],
            )
        lines, width, height = ocr_page_lines(page, scale=self.ocr_scale)
        if cache_file is not None:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(
                json.dumps(
                    {
                        "width": width,
                        "height": height,
                        "lines": [[l.text, l.x0, l.y0, l.x1, l.y1, l.score] for l in lines],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        return _OcrPage(lines=lines, width=width, height=height)


@lru_cache(maxsize=1)
def _ocr_engine():
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


def ocr_page_lines(page, scale: float = 1.6) -> tuple[list[OcrLine], float, float]:
    """OCR one rendered page and return text lines with bounding boxes. Errors propagate."""
    import fitz
    import numpy as np

    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    result, _elapsed = _ocr_engine()(image)
    return lines_from_rapidocr(result), float(pix.width), float(pix.height)


def ocr_page_image(page, scale: float = 1.6) -> str:
    """Plain OCR text for one page in reconstructed reading order ('' on failure)."""
    try:
        lines, width, _height = ocr_page_lines(page, scale=scale)
    except Exception:
        return ""
    text, _columns = order_lines(lines, width)
    return text
