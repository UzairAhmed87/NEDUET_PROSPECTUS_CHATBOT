from pathlib import Path

from app.services.extraction_service import ExtractionService
from tests.fixtures.pdf_factory import PROSPECTUS_PAGES, write_fixture_pdf


def test_extracts_page_numbers_and_text(tmp_path: Path) -> None:
    pdf = write_fixture_pdf(tmp_path / "fixture.pdf", PROSPECTUS_PAGES)
    result = ExtractionService().extract_pdf(pdf)
    assert result.page_count == 5
    assert result.pages[0].page_number == 1
    assert "Civil Engineering" in result.pages[0].text
    assert result.pages[1].page_number == 2
    assert "sixty percent" in result.pages[1].text


def test_empty_page_is_flagged(tmp_path: Path) -> None:
    pdf = write_fixture_pdf(tmp_path / "fixture.pdf", PROSPECTUS_PAGES)
    result = ExtractionService().extract_pdf(pdf)
    empty = [page for page in result.pages if page.is_empty]
    assert empty
    assert empty[0].page_number == 5
    assert result.empty_page_count >= 1


def test_headings_are_detected(tmp_path: Path) -> None:
    pdf = write_fixture_pdf(tmp_path / "fixture.pdf", PROSPECTUS_PAGES)
    result = ExtractionService().extract_pdf(pdf)
    joined = " ".join(result.headings).upper()
    assert "UNDERGRADUATE" in joined or "ADMISSION" in joined
