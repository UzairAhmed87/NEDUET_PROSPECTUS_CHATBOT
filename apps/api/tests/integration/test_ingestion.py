import pytest

from app.core.exceptions import DuplicateDocumentError


def test_ingest_to_vector_store(services, fixture_pdf) -> None:
    result = services["ingestion"].ingest_path(fixture_pdf, title="NED Test Fixture", academic_year="2024-25")
    assert result.document.chunk_count > 0
    assert result.document.page_count == 5
    assert result.document.empty_page_count >= 1
    assert services["registry"].count() == 1
    listed = services["registry"].list_documents()
    assert listed[0].title == "NED Test Fixture"
    assert all(chunk_meta is not None for chunk_meta in [listed[0].document_id])


def test_duplicate_hash_is_rejected(services, fixture_pdf) -> None:
    services["ingestion"].ingest_path(fixture_pdf, title="First")
    with pytest.raises(DuplicateDocumentError):
        services["ingestion"].ingest_path(fixture_pdf, title="Second")


def test_replace_reingests(services, fixture_pdf) -> None:
    first = services["ingestion"].ingest_path(fixture_pdf, title="First")
    second = services["ingestion"].ingest_path(fixture_pdf, title="Replaced", replace=True)
    assert second.replaced is True
    assert second.document.document_id == first.document.document_id
    assert services["registry"].count() == 1
    assert services["registry"].list_documents()[0].title == "Replaced"
