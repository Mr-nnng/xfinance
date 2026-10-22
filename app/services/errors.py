"""Service-layer errors, mapped to HTTP at the API boundary."""

from __future__ import annotations


class ServiceError(Exception):
    status = 500
    code = "internal_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFound(ServiceError):
    status = 404
    code = "not_found"


class BadRequest(ServiceError):
    status = 400
    code = "bad_request"


class DataUnavailable(ServiceError):
    status = 502
    code = "data_unavailable"
