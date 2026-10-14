import pytest

from app.core.exceptions import UnsupportedFileError, ValidationFailed
from app.utils.files import sanitize_filename, validate_pdf_payload


def test_strips_path_traversal_to_basename() -> None:
    assert sanitize_filename("../secret.pdf") == "secret.pdf"
    assert sanitize_filename("folder/nested.pdf") == "nested.pdf"


def test_rejects_non_pdf() -> None:
    with pytest.raises(UnsupportedFileError):
        sanitize_filename("notes.txt")


def test_validates_pdf_header_and_size() -> None:
    with pytest.raises(UnsupportedFileError):
        validate_pdf_payload("file.pdf", b"not-a-pdf", 1000)
    with pytest.raises(ValidationFailed):
        validate_pdf_payload("file.pdf", b"%PDF" + b"x" * 50, 10)
    assert validate_pdf_payload("Prospectus.pdf", b"%PDF-1.4 content", 10_000) == "Prospectus.pdf"
