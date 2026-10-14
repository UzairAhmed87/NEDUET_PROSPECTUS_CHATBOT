from pathlib import Path

from app.core.exceptions import UnsupportedFileError, ValidationFailed

ALLOWED_SUFFIXES = {".pdf"}
UNSAFE_NAME_CHARS = set('<>:"/\\|?*')


def sanitize_filename(filename: str) -> str:
    name = Path(filename.replace("\\", "/")).name
    if not name or name in {".", ".."}:
        raise UnsupportedFileError("A valid PDF filename is required.")
    if any(char in UNSAFE_NAME_CHARS for char in name):
        raise UnsupportedFileError("Filename contains unsafe characters.")
    if ".." in name:
        raise UnsupportedFileError("Filename must not contain path traversal.")
    suffix = Path(name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise UnsupportedFileError("Only PDF files are accepted.")
    return name


def validate_pdf_payload(filename: str, payload: bytes, max_bytes: int) -> str:
    safe_name = sanitize_filename(filename)
    if not payload:
        raise ValidationFailed("Uploaded file is empty.")
    if len(payload) > max_bytes:
        raise ValidationFailed(
            f"File exceeds the {max_bytes // (1024 * 1024)} MB upload limit.",
            details={"size_bytes": len(payload)},
        )
    if not payload.startswith(b"%PDF"):
        raise UnsupportedFileError("File is not a readable PDF (missing PDF header).")
    return safe_name


def unique_destination(directory: Path, filename: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    index = 2
    while True:
        next_candidate = directory / f"{stem}-{index}{suffix}"
        if not next_candidate.exists():
            return next_candidate
        index += 1
