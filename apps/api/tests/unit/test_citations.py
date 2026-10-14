from app.schemas.retrieval import RetrievedChunk
from app.services.answer_service import validate_citations


def _chunk(chunk_id: str, page: int) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id="doc-1",
        document_title="Fixture prospectus",
        document_version="test",
        source_filename="fixture.pdf",
        page_number=page,
        excerpt="excerpt",
        distance=0.1,
        text="full text",
        within_threshold=True,
    )


def test_drops_invented_citation_ids() -> None:
    retrieved = [_chunk("real-1", 2), _chunk("real-2", 3)]
    citations = validate_citations(["real-1", "forged-page-99", "real-1"], retrieved)
    assert [item.chunk_id for item in citations] == ["real-1"]
    assert citations[0].page_number == 2


def test_empty_when_no_overlap() -> None:
    retrieved = [_chunk("real-1", 1)]
    assert validate_citations(["nope"], retrieved) == []
