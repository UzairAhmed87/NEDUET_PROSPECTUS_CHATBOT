from __future__ import annotations

from dataclasses import dataclass

from app.core.exceptions import ValidationFailed
from app.services.extraction_service import ExtractionResult, PageExtraction
from app.services.ocr_layout import section_heading
from app.utils.text import split_paragraphs, split_sentences

SECTION_PATH_DEPTH = 2


@dataclass
class Chunk:
    chunk_id: str
    document_id: str
    document_title: str
    document_version: str | None
    academic_year: str | None
    source_filename: str
    page_number: int
    text: str
    token_estimate: int
    section: str | None = None
    printed_page: str | None = None


class SectionTracker:
    """Tracks the numbered heading path (e.g. '8.1 FEE AND CHARGES > 8.1.2 For TIEST')."""

    def __init__(self) -> None:
        self._stack: list[tuple[int, str]] = []

    def observe(self, unit: str) -> None:
        first_line = unit.strip().split("\n", 1)[0]
        found = section_heading(first_line)
        if not found:
            return
        number, title = found
        depth = number.count(".") + 1
        self._stack = [item for item in self._stack if item[0] < depth]
        self._stack.append((depth, f"{number} {title}"))

    @property
    def label(self) -> str | None:
        if not self._stack:
            return None
        return " > ".join(title for _depth, title in self._stack[-SECTION_PATH_DEPTH:])


class ChunkingService:
    def __init__(self, chunk_size_chars: int, overlap_chars: int, *, section_headers: bool = False) -> None:
        if chunk_size_chars < 200:
            raise ValidationFailed("CHUNK_SIZE_CHARS must be at least 200.")
        if overlap_chars < 0 or overlap_chars >= chunk_size_chars:
            raise ValidationFailed("CHUNK_OVERLAP_CHARS must be >= 0 and smaller than chunk size.")
        self.chunk_size_chars = chunk_size_chars
        self.overlap_chars = overlap_chars
        self.section_headers = section_headers

    def config(self) -> dict:
        return {
            "chunk_size_chars": self.chunk_size_chars,
            "chunk_overlap_chars": self.overlap_chars,
            "section_headers": self.section_headers,
        }

    def chunk_extraction(
        self,
        extraction: ExtractionResult,
        *,
        document_id: str,
        document_title: str,
        document_version: str | None,
        academic_year: str | None,
        source_filename: str,
    ) -> list[Chunk]:
        chunks: list[Chunk] = []
        sequence = 0
        tracker = SectionTracker()
        for page in extraction.pages:
            if page.is_empty or not page.text.strip():
                continue
            for piece, section in self._chunk_page(page, tracker):
                sequence += 1
                text = f"Section: {section}\n{piece}" if self.section_headers and section else piece
                chunks.append(
                    Chunk(
                        chunk_id=f"{document_id}-p{page.page_number}-c{sequence:04d}",
                        document_id=document_id,
                        document_title=document_title,
                        document_version=document_version,
                        academic_year=academic_year,
                        source_filename=source_filename,
                        page_number=page.page_number,
                        text=text,
                        token_estimate=max(1, len(text) // 4),
                        section=section,
                        printed_page=page.printed_page,
                    )
                )
        if not chunks:
            raise ValidationFailed(
                "No indexable text chunks were produced. Image-only pages were skipped."
            )
        return chunks

    def _chunk_page(self, page: PageExtraction, tracker: SectionTracker) -> list[tuple[str, str | None]]:
        chunks: list[tuple[str, str | None]] = []
        current = ""
        current_section: str | None = tracker.label
        has_new_content = False

        def flush() -> None:
            nonlocal current, has_new_content
            text = current.strip()
            if text and has_new_content and (not chunks or chunks[-1][0] != text):
                chunks.append((text, current_section))
            current = ""
            has_new_content = False

        for unit in self._split_units(page.text):
            tracker.observe(unit)
            if not has_new_content:
                current_section = tracker.label
            candidate = f"{current}\n\n{unit}" if current else unit
            if len(candidate) <= self.chunk_size_chars:
                current = candidate
                has_new_content = True
                continue
            overlap = self._overlap_prefix(current) if has_new_content else current
            flush()
            current_section = tracker.label
            current = f"{overlap}\n\n{unit}".strip() if overlap else unit
            has_new_content = True
            if len(current) > self.chunk_size_chars:
                pieces = self._hard_wrap(current)
                for piece in pieces[:-1]:
                    chunks.append((piece, current_section))
                current = pieces[-1] if pieces else ""
        flush()
        return chunks

    def _split_units(self, text: str) -> list[str]:
        units: list[str] = []
        for paragraph in split_paragraphs(text):
            if len(paragraph) <= self.chunk_size_chars:
                units.append(paragraph)
                continue
            sentence_buffer = ""
            for sentence in split_sentences(paragraph):
                if not sentence_buffer:
                    sentence_buffer = sentence
                    continue
                merged = f"{sentence_buffer} {sentence}"
                if len(merged) <= self.chunk_size_chars:
                    sentence_buffer = merged
                else:
                    units.append(sentence_buffer)
                    sentence_buffer = sentence
            if sentence_buffer:
                units.append(sentence_buffer)
        return units

    def _overlap_prefix(self, text: str) -> str:
        if self.overlap_chars == 0 or len(text) <= self.overlap_chars:
            return text
        tail = text[-self.overlap_chars :]
        space = tail.find(" ")
        if 0 <= space < len(tail) - 1:
            return tail[space + 1 :].strip()
        return tail.strip()

    def _hard_wrap(self, text: str) -> list[str]:
        pieces: list[str] = []
        remaining = text
        size = self.chunk_size_chars
        while len(remaining) > size:
            window = remaining[:size]
            split_at = window.rfind(" ")
            if split_at < size * 0.5:
                split_at = size
            pieces.append(remaining[:split_at].strip())
            remaining = remaining[split_at:].strip()
            if self.overlap_chars and pieces:
                prefix = self._overlap_prefix(pieces[-1])
                remaining = f"{prefix} {remaining}".strip()
                if remaining == prefix:
                    break
        if remaining:
            pieces.append(remaining)
        return pieces
