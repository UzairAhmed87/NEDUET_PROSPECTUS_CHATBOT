from app.repositories.vector_store import VectorHit
from app.services.retrieval_service import _to_retrieved


def test_within_threshold_uses_max_distance() -> None:
    hit = VectorHit(
        chunk_id="c1",
        text="Eligibility requires sixty percent marks.",
        distance=0.4,
        metadata={
            "document_id": "doc-1",
            "document_title": "Fixture",
            "source_filename": "f.pdf",
            "page_number": 2,
        },
    )
    accepted = _to_retrieved(hit, max_distance=0.55)
    rejected = _to_retrieved(hit, max_distance=0.2)
    assert accepted.within_threshold is True
    assert rejected.within_threshold is False
    assert accepted.page_number == 2


def test_excerpt_and_metadata_survive() -> None:
    hit = VectorHit(
        chunk_id="c1",
        text="A" * 500,
        distance=0.1,
        metadata={"document_title": "NED fixture", "page_number": 1, "document_id": "d"},
    )
    retrieved = _to_retrieved(hit, 0.5)
    assert retrieved.document_title == "NED fixture"
    assert retrieved.excerpt.endswith("…")
    assert len(retrieved.excerpt) <= 280
