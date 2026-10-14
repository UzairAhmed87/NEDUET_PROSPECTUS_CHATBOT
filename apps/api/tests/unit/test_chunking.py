from app.services.chunking_service import ChunkingService
from app.services.extraction_service import ExtractionResult, PageExtraction


def _page(number: int, text: str) -> PageExtraction:
    return PageExtraction(
        page_number=number,
        text=text,
        char_count=len(text),
        image_count=0,
        is_empty=not text.strip(),
        needs_ocr=False,
    )


def test_chunking_preserves_page_metadata() -> None:
    extraction = ExtractionResult(
        page_count=2,
        pages=[
            _page(1, "Paragraph one about civil programmes.\n\nParagraph two about electrical programmes."),
            _page(2, "Eligibility requires a qualifying examination with documented marks."),
        ],
        extractable_char_count=200,
    )
    chunks = ChunkingService(400, 40).chunk_extraction(
        extraction,
        document_id="doc-1",
        document_title="Fixture",
        document_version="test",
        academic_year="2024-25",
        source_filename="fixture.pdf",
    )
    assert chunks
    assert all(chunk.document_id == "doc-1" for chunk in chunks)
    assert {chunk.page_number for chunk in chunks} == {1, 2}
    assert all(chunk.chunk_id.startswith("doc-1-") for chunk in chunks)


def test_overlap_keeps_boundary_words() -> None:
    paragraph = " ".join(f"token{i:03d}" for i in range(80))
    extraction = ExtractionResult(
        page_count=1,
        pages=[_page(1, paragraph)],
        extractable_char_count=len(paragraph),
    )
    service = ChunkingService(chunk_size_chars=220, overlap_chars=40)
    chunks = service.chunk_extraction(
        extraction,
        document_id="doc-1",
        document_title="Fixture",
        document_version=None,
        academic_year=None,
        source_filename="fixture.pdf",
    )
    assert len(chunks) >= 2
    first_tail = chunks[0].text[-40:]
    assert any(word in chunks[1].text for word in first_tail.split() if len(word) > 4)


def test_empty_pages_are_not_chunked() -> None:
    extraction = ExtractionResult(
        page_count=2,
        pages=[_page(1, "Indexed paragraph about scholarships."), _page(2, "")],
        extractable_char_count=40,
        empty_page_count=1,
    )
    chunks = ChunkingService(400, 40).chunk_extraction(
        extraction,
        document_id="doc-1",
        document_title="Fixture",
        document_version=None,
        academic_year=None,
        source_filename="fixture.pdf",
    )
    assert all(chunk.page_number == 1 for chunk in chunks)
