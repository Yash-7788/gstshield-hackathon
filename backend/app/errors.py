"""Fixed public failures; never put supplied values or SQL in messages."""


class APIError(Exception):
    def __init__(self, status: int, code: str, message: str, *, retry_after: int = 0):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.retry_after = retry_after


class StorageError(RuntimeError):
    """Safe to display to the operator."""
