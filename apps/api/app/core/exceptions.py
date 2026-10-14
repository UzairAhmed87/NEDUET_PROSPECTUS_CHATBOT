from typing import Any


class AppError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str = "APP_ERROR",
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class ValidationFailed(AppError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="VALIDATION_ERROR", status_code=422, details=details)


class DuplicateDocumentError(AppError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="DUPLICATE_DOCUMENT", status_code=409, details=details)


class DocumentNotFoundError(AppError):
    def __init__(self, message: str = "Document not found.") -> None:
        super().__init__(message, code="DOCUMENT_NOT_FOUND", status_code=404)


class UnsupportedFileError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="UNSUPPORTED_FILE", status_code=400)


class ExtractionError(AppError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="EXTRACTION_ERROR", status_code=400, details=details)


class ProviderConfigurationError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="PROVIDER_NOT_CONFIGURED", status_code=503)


class ProviderError(AppError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code="PROVIDER_ERROR", status_code=502, details=details)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Admin credentials are required.") -> None:
        super().__init__(message, code="UNAUTHORIZED", status_code=401)
